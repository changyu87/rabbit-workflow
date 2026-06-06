#!/usr/bin/env python3
"""merge-prs.py — squash-merge a list of PRs after delegating to safety-check.py.

Usage:
  merge-prs.py <pr-list>

Where <pr-list> is a comma-separated list of PR numbers.

Per rabbit-auto-evolve spec.md Inv 6 / Inv 61, for each PR this script:
  1. Verifies the PR base via `gh pr view <#> --json baseRefName -q .baseRefName`.
     During the dev<->main coexistence window (Inv 61), the accepted bases are
     `{dev, main}` (integration_target.accepted_targets()). If base is NEITHER
     it records {pr, status:"skipped", reason:"base-not-accepted"} and
     continues. The local accepted-set check is defense-in-depth above
     safety-check.py — `gh pr merge` is NEVER invoked on an out-of-set base.
  2. Invokes `safety-check.py <pr#> --phase merge`. If it exits non-zero,
     records {pr, status:"skipped", reason:"safety-check-failed"}.
  3. Otherwise calls `gh pr merge <#> --squash` (a direct squash merge — NOT
     `--auto`; see issue #429: `--auto` requires the repo to have auto-merge
     enabled and fails on repos without it). Inv 61 / issue #973: when the PR's
     base IS the default branch (main, which is branch-protected with a
     required review the bot cannot satisfy on its own PR) the merge adds
     `--admin` (`gh pr merge <#> --squash --admin`) to override ONLY that
     structural required-review; a `dev`-base merge (non-default branch, no
     required-review protection) keeps the plain `--squash` with NO `--admin`.
     `enforce_admins: false` permits the admin override, and the loop's REAL
     quality gate (the contract repo-gate, run pre-merge) is unchanged. On
     success records {pr, status:"merged"}; on failure records
     {pr, status:"failed", reason:"gh-merge-failed: <stderr>"}.
  4. After a successful merge, parses the merged PR TITLE and body for
     `Fixes #N` / `Closes #N` / `Resolves #N` references (case-insensitive,
     unioned across title and body — issue #868: a title-only ref still
     closes) and explicitly closes each referenced issue via
     `item-status.py close <N> --reason completed --commit-sha <merge-sha>
     --comment "...<sha>..."`. Because `gh pr merge --squash` creates the
     squash commit on the REMOTE `dev` only, the SHA is not yet in the local
     repo; so before the first close this script runs
     `git fetch origin <sha>` (falling back to `git fetch origin dev`) to make
     the SHA locally resolvable — NEVER `git merge` (permission-denied in the
     loop environment). The fetch is best-effort and never fails the merge.
     The `--commit-sha` is REQUIRED by
     item-status.py for a `completed` closure (issue #423 Part C): a
     completed closure must point at the real merge commit that landed the
     work. GitHub's native auto-close only fires for default-branch (`main`)
     merges; while the integration target is `dev` (a non-default branch),
     without this step referenced issues would stay open indefinitely.
     Successfully-closed issue numbers are recorded under `closed_issues`;
     issues whose close command failed are recorded under `close_failed` and a
     warning is written to stderr — a close failure never fails the merge.
     Inv 61: this whole manual-close step is CONDITIONAL on the PR's base —
     the branch it merged INTO — NOT being the default branch (the native
     close fires based on the merged-into branch). It runs for a `dev`-base
     merge and is skipped for a `main`-base merge (native auto-close fires).
     The merge SHA is still recorded under `last_merged_sha` in either case.

The aggregated per-PR result list is emitted as JSON on stdout. The script
exits 0 except on argparse / unexpected error — partial-outcome reporting
is the caller's responsibility.

The sibling `safety-check.py` is resolved via the
RABBIT_AUTO_EVOLVE_SCRIPT_DIR env var when set; otherwise it falls back to
this script's own dirname. This allows tests to inject a shim without
touching the real safety-check.py. The cross-feature `item-status.py` is
resolved via the RABBIT_ISSUE_SCRIPT_DIR env var when set; otherwise it
falls back to `.claude/features/rabbit-issue/scripts/` relative to the
repo root inferred from this script's path.

With `--record-pending` (issue #499), after processing the PR list this
script appends every successfully-merged PR number to the
`pending_post_merge` array in `<state_dir>/auto-evolve-state.json` (read-
modify-write, de-duplicated, atomic via temp+rename). The state dir resolves
via the RABBIT_AUTO_EVOLVE_STATE_DIR env var when set, else `<cwd>/.rabbit`
(matching update-state.py). `run-post-merge.py` later drains this list to run
tick phases 8-10. Without `--record-pending` no state write occurs and the
behavior is unchanged.

The SAME `--record-pending` write also records `last_merged_sha` (issue
#564): the merge commit SHA of the LAST successfully-merged PR (the
`mergeCommit.oid` already fetched per the Inv 6 close-after-merge step) is
written into the state file in the same read-modify-write. No phase script
previously persisted this informational field (surfaced by
status-report.py), so it lagged perpetually; phase 11's deterministic
re-read (update-state.py, Inv 40) now captures it off disk — it is never
dispatcher hand-set. A run with no merge leaves `last_merged_sha` untouched.

Issue #838 (Inv 54): the SAME `--record-pending` read-modify-write also
promotes the dispatch_journal entry of every issue a merged PR closed to
`completed` (recording its PR number) — the journal's `completed` transition,
no new write site.

Version: 1.9.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Resolved relative to THIS file's dir (the real scripts dir) — NOT via
# RABBIT_AUTO_EVOLVE_SCRIPT_DIR, which tests repoint at a shim dir. The
# integration-target abstraction (Inv 61) is a sibling library, never shimmed.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integration_target  # noqa: E402

# Matches GitHub's closing-keyword references: Fixes/Closes/Resolves #N
# (and their common variants), case-insensitive. Captures the issue number.
_CLOSE_REF_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b\s*#(\d+)",
    re.IGNORECASE,
)


def _script_dir():
    return os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
                          os.path.dirname(os.path.abspath(__file__)))


def _issue_script_dir():
    override = os.environ.get("RABBIT_ISSUE_SCRIPT_DIR")
    if override:
        return override
    # this script lives at .claude/features/rabbit-auto-evolve/scripts/
    here = os.path.dirname(os.path.abspath(__file__))
    features = os.path.normpath(os.path.join(here, "..", ".."))
    return os.path.join(features, "rabbit-issue", "scripts")


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _promote_journal_completed(state, completed_map):
    """Mark each issue's dispatch_journal entry `completed` and record its `pr`
    (issue #838, Inv 54) — the SAME read-modify-write that appends to
    pending_post_merge. `completed_map` is {issue: pr} for every issue the
    merged PRs closed. An issue with no journal entry is silently skipped (the
    journal is a local accelerant, not a source of truth). Mutates `state` in
    place; no-op when there is no journal."""
    if not completed_map:
        return
    journal = state.get("dispatch_journal")
    if not isinstance(journal, dict):
        return
    for tick in journal.values():
        if not isinstance(tick, dict):
            continue
        for e in tick.get("entries", []):
            if not isinstance(e, dict):
                continue
            issue = e.get("issue")
            if issue in completed_map:
                e["status"] = "completed"
                e["pr"] = completed_map[issue]


def _record_pending(merged_prs, last_merged_sha=None, completed_map=None):
    """Append `merged_prs` to pending_post_merge in the state file (issue
    #499), record `last_merged_sha` when a merge happened (issue #564), and
    promote the dispatch_journal entries of issues those merges closed to
    `completed` (issue #838, Inv 54) — all in ONE read-modify-write.
    De-duplicated, order-preserving, atomic via temp+rename. Best-effort: a
    missing/malformed state file or write error emits a stderr warning and
    never fails the merge run (the per-PR result array on stdout is the
    authoritative outcome).

    `last_merged_sha` (the merge commit SHA of the last successfully-merged
    PR) is written ONLY when truthy: a run with no merge leaves the field
    untouched. Phase 11's deterministic re-read (update-state.py, Inv 40)
    later captures it off disk — it is never dispatcher hand-set."""
    if not merged_prs:
        return
    state_dir = _state_dir()
    state_path = os.path.join(state_dir, "auto-evolve-state.json")
    try:
        with open(state_path) as f:
            state = json.load(f)
    except (OSError, ValueError) as e:
        sys.stderr.write(
            f"merge-prs: --record-pending: cannot read state file "
            f"{state_path}: {e}\n"
        )
        return
    existing = state.get("pending_post_merge") or []
    seen = set(existing)
    combined = list(existing)
    for pr in merged_prs:
        if pr not in seen:
            seen.add(pr)
            combined.append(pr)
    state["pending_post_merge"] = combined
    if last_merged_sha:
        state["last_merged_sha"] = last_merged_sha
    _promote_journal_completed(state, completed_map or {})
    tmp_path = state_path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, state_path)
    except OSError as e:
        sys.stderr.write(
            f"merge-prs: --record-pending: write failed: {e}\n"
        )
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _pr_base(pr):
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr),
         "--json", "baseRefName", "-q", ".baseRefName"],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr


def _safety_check(pr):
    safety = os.path.join(_script_dir(), "safety-check.py")
    return subprocess.run(
        [sys.executable, safety, str(pr), "--phase", "merge"],
        capture_output=True, text=True,
    )


def _gh_merge(pr, admin=False):
    # Direct squash merge — NOT `--auto`. The `--auto` flag requires the repo
    # to have auto-merge enabled (enablePullRequestAutoMerge); on repos without
    # it, `gh pr merge --auto` fails for any PR that is not immediately
    # mergeable with "Auto merge is not allowed for this repository" (issue
    # #429). Mergeability is already gated by the base-not-accepted refusal in
    # process() plus safety-check.py, so a direct merge is correct and does
    # not depend on the repo's auto-merge setting.
    #
    # Issue #973 (Inv 61): when `admin` is set — i.e. the PR base is the
    # protected default branch (main) — add `--admin` so the loop can land its
    # OWN PRs despite `main`'s required_approving_review_count: 1 protection
    # (the bot cannot approve its own PR). `enforce_admins: false` permits the
    # admin override; `--admin` bypasses ONLY the structural required-review,
    # never the loop's real quality gate (the contract repo-gate, run
    # pre-merge). A `dev`-base merge (non-default branch, no required-review
    # protection) keeps the plain `--squash` with NO `--admin`.
    cmd = ["gh", "pr", "merge", str(pr), "--squash"]
    if admin:
        cmd.append("--admin")
    return subprocess.run(cmd, capture_output=True, text=True)


def _pr_field(pr, field, query):
    """Return the stripped value of a single `gh pr view` json field, or ''
    if the view fails (best-effort — never raises)."""
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr), "--json", field, "-q", query],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _parse_close_refs(*texts):
    """Return the sorted, de-duplicated list of issue numbers referenced by a
    closing keyword (Fixes/Closes/Resolves #N) across all `texts`.

    Issue #868: callers pass BOTH the PR title and the PR body so a close-ref
    in the title ALONE also closes its issue. PRs merge into `dev` (not the
    default branch), so GitHub's native auto-close never fires; this explicit
    parse is the loop's only close path. Numbers found across the texts are
    unioned, so a ref present in both title and body is closed once."""
    nums = set()
    for text in texts:
        nums.update(int(m) for m in _CLOSE_REF_RE.findall(text or ""))
    return sorted(nums)


def _item_status_close(num, sha):
    """Invoke item-status.py close on `num`. Returns the CompletedProcess.
    Idempotent against already-closed issues.

    Per issue #423 (Part C), `item-status.py close --reason completed` now
    REQUIRES `--commit-sha <sha>` that resolves to a real commit — a
    completed closure must point at the merge commit that landed the work.
    We always pass the merge SHA fetched from `gh pr view`; if it is empty
    (best-effort fetch failed) item-status.py rejects the close and the
    failure is recorded under close_failed (never fails the merge)."""
    item_status = os.path.join(_issue_script_dir(), "item-status.py")
    comment = f"TDD cycle complete in {sha}" if sha else "TDD cycle complete"
    return subprocess.run(
        [sys.executable, item_status, "close", str(num),
         "--reason", "completed", "--commit-sha", sha, "--comment", comment],
        capture_output=True, text=True,
    )


def _fetch_merge_sha(sha):
    """Make the just-merged squash commit SHA resolvable in the LOCAL repo
    before the close step (issue #802). `gh pr merge --squash` creates the
    squash commit on the REMOTE `dev` only; the local repo has not seen it
    yet, so `item-status.py close --commit-sha <sha>` (which requires the SHA
    to resolve to a real LOCAL commit, #423 Part C) would fail in a headless
    tick with no dispatcher to recover.

    Run `git fetch origin <sha>` (the specific object); if that fails — some
    remotes reject fetching an arbitrary SHA — fall back to
    `git fetch origin dev`, which also lands the squash commit. NEVER `git
    merge` (a permission-denied operation in the loop's environment); a plain
    fetch lands the object without touching the working tree. Best-effort: any
    fetch failure emits a stderr warning and returns so the close still runs
    (and records close_failed if the SHA is still unresolvable). Never raises;
    never fails the merge."""
    if not sha:
        return
    proc = subprocess.run(
        ["git", "fetch", "origin", sha],
        capture_output=True, text=True,
    )
    if proc.returncode == 0:
        return
    proc = subprocess.run(
        ["git", "fetch", "origin", "dev"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(
            f"warning: git fetch of merge SHA {sha} failed "
            f"(close may not resolve it locally): {proc.stderr.strip()}\n"
        )


def _close_referenced_issues(pr, result):
    """After a successful merge, close every issue referenced by a closing
    keyword in the PR title OR body. Mutates `result` in place, adding
    `closed_issues` and `close_failed`. A close failure never fails the merge.

    Issue #868: the close-ref scan unions the title and the body, so a
    subagent that put `Closes #N` in the title alone still closes its issue —
    PRs merge into `dev`, where GitHub's native auto-close never fires, so this
    explicit parse is the loop's only close path.

    Also records the fetched merge commit SHA under `result["merge_sha"]`
    (issue #564) so `_record_pending` can persist it as `last_merged_sha`."""
    title = _pr_field(pr, "title", ".title")
    body = _pr_field(pr, "body", ".body")
    sha = _pr_field(pr, "mergeCommit", ".mergeCommit.oid")
    result["merge_sha"] = sha
    refs = _parse_close_refs(title, body)
    # Make the squash SHA resolvable locally before any close (issue #802).
    if refs:
        _fetch_merge_sha(sha)
    closed, failed = [], []
    for num in refs:
        proc = _item_status_close(num, sha)
        if proc.returncode == 0:
            closed.append(num)
        else:
            failed.append(num)
            sys.stderr.write(
                f"warning: failed to close issue #{num} after merging "
                f"PR #{pr}: {proc.stderr.strip()}\n"
            )
    result["closed_issues"] = closed
    result["close_failed"] = failed


def process(pr):
    rc, base, stderr = _pr_base(pr)
    if rc != 0:
        return {"pr": pr, "status": "skipped",
                "reason": f"gh-view-failed: {stderr.strip()}"}
    # Inv 61 — accept any base in the coexistence set ({dev, main}); refuse a
    # base that is neither. Defense-in-depth above safety-check.py: `gh pr
    # merge` is NEVER invoked on an out-of-set base.
    if base not in integration_target.accepted_targets():
        return {"pr": pr, "status": "skipped", "reason": "base-not-accepted"}

    sc = _safety_check(pr)
    if sc.returncode != 0:
        return {"pr": pr, "status": "skipped",
                "reason": "safety-check-failed"}

    # Inv 61 / issue #973 — a merge whose base IS the default branch (main) is
    # blocked by `main`'s required-review protection (the bot cannot approve its
    # own PR), so it uses an admin-override merge (`--admin`); a `dev`-base
    # merge (non-default branch, no required-review protection) keeps the plain
    # `--squash`. The same default-branch axis drives the manual-close skip
    # below — keeping the two consistent (main ⇒ --admin AND skip manual close;
    # dev ⇒ no --admin AND run manual close).
    on_default_branch = integration_target.is_default_branch(base)
    merge = _gh_merge(pr, admin=on_default_branch)
    if merge.returncode != 0:
        return {"pr": pr, "status": "failed",
                "reason": f"gh-merge-failed: {merge.stderr.strip()}"}

    result = {"pr": pr, "status": "merged"}
    # Inv 61 — the manual close-after-merge exists ONLY because a merge to a
    # non-default branch (dev) does not trigger GitHub's native keyword
    # auto-close. GitHub fires the native close based on the branch the PR
    # actually merged INTO, so the decision keys on the PR base: when the base
    # IS the default branch (main) the native close fires and the manual path
    # is skipped as redundant; while the base is dev (a non-default branch) the
    # loop runs the explicit close. The merge SHA is still recorded
    # (last_merged_sha, issue #564) so the informational state field stays
    # current under either base.
    if on_default_branch:
        result["merge_sha"] = _pr_field(pr, "mergeCommit", ".mergeCommit.oid")
        result["closed_issues"] = []
        result["close_failed"] = []
    else:
        _close_referenced_issues(pr, result)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Squash-merge each PR in <pr-list> (comma-separated) "
                    "after delegating to safety-check.py. Refuses to merge "
                    "PRs whose base is outside the {dev, main} coexistence "
                    "set (Inv 61). Emits per-PR result JSON "
                    "array on stdout; always exit 0 except argparse error."
    )
    parser.add_argument("pr_list",
                        help="comma-separated list of PR numbers, e.g. '12,34'")
    parser.add_argument(
        "--record-pending", action="store_true",
        help="append successfully-merged PR numbers to pending_post_merge in "
             ".rabbit/auto-evolve-state.json (issue #499) so run-post-merge.py "
             "drains them through tick phases 8-10",
    )
    args = parser.parse_args()

    try:
        prs = [int(s.strip()) for s in args.pr_list.split(",") if s.strip()]
    except ValueError as e:
        parser.error(f"invalid pr_list: {e}")

    results = [process(pr) for pr in prs]

    if args.record_pending:
        merged_rows = [r for r in results if r.get("status") == "merged"]
        merged = [r["pr"] for r in merged_rows]
        # The merge commit SHA of the LAST successfully-merged PR (issue
        # #564). Empty when no merge happened or the SHA fetch failed → the
        # state field is then left untouched.
        last_sha = merged_rows[-1].get("merge_sha") if merged_rows else None
        # {issue: pr} for every issue a merged PR closed (issue #838, Inv 54)
        # so its dispatch_journal entry is promoted to `completed`.
        completed_map = {}
        for r in merged_rows:
            for issue in r.get("closed_issues", []):
                completed_map[issue] = r["pr"]
        _record_pending(merged, last_merged_sha=last_sha,
                        completed_map=completed_map)

    # `merge_sha` is an internal handoff field (issue #564), not part of the
    # documented per-PR result JSON contract — strip it before emitting.
    for r in results:
        r.pop("merge_sha", None)

    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
