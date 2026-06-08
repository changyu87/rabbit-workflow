#!/usr/bin/env python3
"""merge-prs.py — squash-merge a list of PRs after delegating to safety-check.py.

Usage:
  merge-prs.py <pr-list>

Where <pr-list> is a comma-separated list of PR numbers.

Per rabbit-auto-evolve spec.md Inv 6 / Inv 61, for each PR this script:
  1. Verifies the PR base via `gh pr view <#> --json baseRefName -q .baseRefName`.
     The sole accepted base is the integration target `main`
     (integration_target.accepted_targets()); the dev<->main coexistence window
     has closed, so the legacy `dev` base is now refused along with any other.
     If the base is not `main` it records
     {pr, status:"skipped", reason:"base-not-accepted"} and continues. The
     local accepted-set check is defense-in-depth above safety-check.py —
     `gh pr merge` is NEVER invoked on an out-of-set base.
  2. Invokes `safety-check.py <pr#> --phase merge`. If it exits non-zero,
     records {pr, status:"skipped", reason:"safety-check-failed"}.
  3. Otherwise calls `gh pr merge <#> --squash --admin` (a direct squash merge
     — NOT `--auto`; see issue #429: `--auto` requires the repo to have
     auto-merge enabled and fails on repos without it). Inv 61 / issue #973:
     every accepted base is the protected default branch (`main`, branch-
     protected with a required review the bot cannot satisfy on its own PR), so
     every merge adds `--admin` to override ONLY that structural required-review.
     `enforce_admins: false` permits the admin override, and the loop's REAL
     quality gate (the contract repo-gate, run pre-merge) is unchanged. On
     success records {pr, status:"merged"}; on failure records
     {pr, status:"failed", reason:"gh-merge-failed: <stderr>"}.
  4. After a successful merge, parses the merged PR TITLE and body for
     `Fixes #N` / `Closes #N` / `Resolves #N` references (case-insensitive,
     unioned across title and body — issue #868: a title-only ref still
     counts), then CROSS-CHECKS each `#N` against `gh issue view <N> --json
     state` and keeps ONLY currently-OPEN issues (issue #1101 / Inv 68), and
     records that filtered, sorted set under `closed_issues`. The cross-check
     defeats the enumeration trap: GitHub's closing grammar treats `Fix #N` as
     a closing keyword, so a PR body listing `Fix #1 / Fix #2 / Fix #3` would
     otherwise record #1/#2/#3 (PR numbers / closed issues the PR never
     targeted); a non-open `#N` is dropped (logged to stderr, never recorded).
     Because the merge targets the default branch `main`, GitHub's native
     keyword auto-close fires for every referenced issue; the loop performs NO
     manual close. The filtered set exists solely so the dispatch-journal
     promotion (Inv 54) can mark those entries `completed` — native auto-close
     does not report the closed set back to the loop, and the loop's recorded
     bookkeeping must be accurate (open-only) even if GitHub's own auto-close is
     broader. The merge SHA is recorded under `last_merged_sha`.

The aggregated per-PR result list is emitted as JSON on stdout. The script
exits 0 except on argparse / unexpected error — partial-outcome reporting
is the caller's responsibility.

The sibling `safety-check.py` is resolved via the
RABBIT_AUTO_EVOLVE_SCRIPT_DIR env var when set; otherwise it falls back to
this script's own dirname. This allows tests to inject a shim without
touching the real safety-check.py.

With `--record-pending` (issue #499), after processing the PR list this
script appends every successfully-merged PR number to the
`pending_post_merge` array in `<state_dir>/auto-evolve-state.json` (read-
modify-write, de-duplicated, atomic via temp+rename). The state dir resolves
via the RABBIT_AUTO_EVOLVE_STATE_DIR env var when set, else `<cwd>/.rabbit`
(matching update-state.py). `run-post-merge.py` later drains this list to run
tick phases 8-10. Without `--record-pending` no state write occurs and the
behavior is unchanged.

The SAME `--record-pending` write also records `last_merged_sha` (issue
#564): the merge commit SHA of the LAST successfully-merged PR
(`mergeCommit.oid`) is written into the state file in the same read-modify-
write. No phase script previously persisted this informational field (surfaced
by status-report.py), so it lagged perpetually; phase 11's deterministic
re-read (update-state.py, Inv 40) now captures it off disk — it is never
dispatcher hand-set. A run with no merge leaves `last_merged_sha` untouched.

Issue #838 (Inv 54): the SAME `--record-pending` read-modify-write also
promotes the dispatch_journal entry of every issue a merged PR closed to
`completed` (recording its PR number), deriving the closed set from the PR's
parsed close-refs — the journal's `completed` transition, no new write site.

Version: 2.1.0
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
    # Issue #973 (Inv 61): when `admin` is set — every accepted base is now the
    # protected default branch (main) — add `--admin` so the loop can land its
    # OWN PRs despite `main`'s required_approving_review_count: 1 protection
    # (the bot cannot approve its own PR). `enforce_admins: false` permits the
    # admin override; `--admin` bypasses ONLY the structural required-review,
    # never the loop's real quality gate (the contract repo-gate, run
    # pre-merge).
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
    in the title ALONE is also captured. Numbers found across the texts are
    unioned, so a ref present in both title and body appears once.

    Inv 61: every merge targets the default branch `main`, so GitHub's native
    keyword auto-close fires for every referenced issue. The loop no longer
    closes issues itself; this parse exists only to derive the SET of issues a
    merge closed (native auto-close does not report that set back) so the
    dispatch-journal promotion (Inv 54) can mark their entries `completed`.

    NOTE: this is the RAW parse. GitHub's closing grammar treats `Fix #N` as a
    closing keyword even when the author meant a bare enumeration (`Fix #1 /
    Fix #2 / Fix #3`), so the raw set can carry numbers the PR never targeted.
    Callers MUST pass the result through `_filter_open_issues` before recording
    it (issue #1101 — the close-ref open-issue cross-check guard)."""
    nums = set()
    for text in texts:
        nums.update(int(m) for m in _CLOSE_REF_RE.findall(text or ""))
    return sorted(nums)


def _issue_is_open(num):
    """Return True iff `#num` is a currently-OPEN GitHub issue, via
    `gh issue view <num> --json state -q .state` (state == "OPEN",
    case-insensitive). Best-effort: a non-zero exit (the number is a PR, not an
    issue, or otherwise unviewable) is treated as NOT-open, so a non-issue
    enumeration number is dropped rather than recorded (issue #1101)."""
    proc = subprocess.run(
        ["gh", "issue", "view", str(num),
         "--json", "state", "-q", ".state"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return False
    return proc.stdout.strip().upper() == "OPEN"


def _filter_open_issues(nums):
    """Filter a raw close-ref set down to those that are currently-OPEN issues
    (issue #1101). GitHub's closing grammar treats `Fix #N` as a closing
    keyword, so a PR body enumerating `Fix #1 / Fix #2 / Fix #3` wrongly yields
    #1/#2/#3 in the raw parse. Cross-checking each `#N` against
    `gh issue view` (open?) drops every number that is NOT a live issue this PR
    plausibly targets — a PR number, an already-closed issue, or a bare
    enumeration — so the recorded `closed_issues` (and the loop bookkeeping
    that derives from it) can never wrongly mark an unrelated issue closed.
    A dropped ref is logged to stderr (observability), never acted on."""
    kept = []
    for n in nums:
        if _issue_is_open(n):
            kept.append(n)
        else:
            sys.stderr.write(
                f"merge-prs: dropping close-ref #{n}: not a currently-open "
                f"issue (issue #1101 enumeration guard)\n"
            )
    return kept


def process(pr):
    rc, base, stderr = _pr_base(pr)
    if rc != 0:
        return {"pr": pr, "status": "skipped",
                "reason": f"gh-view-failed: {stderr.strip()}"}
    # Inv 61 — the sole accepted base is the default branch `main`
    # (accepted_targets()). A base that is anything else (including the legacy
    # `dev`) is refused. Defense-in-depth above safety-check.py: `gh pr merge`
    # is NEVER invoked on an out-of-set base.
    if base not in integration_target.accepted_targets():
        return {"pr": pr, "status": "skipped", "reason": "base-not-accepted"}

    sc = _safety_check(pr)
    if sc.returncode != 0:
        return {"pr": pr, "status": "skipped",
                "reason": "safety-check-failed"}

    # Inv 61 / issue #973 — every accepted base is the protected default branch
    # (`main`), whose required review the bot cannot satisfy on its own PR, so
    # every merge uses an admin-override (`gh pr merge <#> --squash --admin`) to
    # bypass ONLY that structural required-review (`enforce_admins: false`
    # permits it; the real quality gate, the contract repo-gate run pre-merge,
    # is unchanged).
    merge = _gh_merge(pr, admin=True)
    if merge.returncode != 0:
        return {"pr": pr, "status": "failed",
                "reason": f"gh-merge-failed: {merge.stderr.strip()}"}

    result = {"pr": pr, "status": "merged"}
    # Inv 61 — the merge targeted the default branch `main`, so GitHub's native
    # `Fixes/Closes/Resolves` keyword auto-close fires for every referenced
    # issue; the loop performs NO manual close. We still parse the PR's
    # close-refs (title + body union, issue #868) into `closed_issues` so the
    # dispatch-journal promotion (Inv 54) can mark those entries `completed` —
    # native auto-close does not report the closed set back to the loop. The
    # merge SHA is recorded (last_merged_sha, issue #564) for the informational
    # state field.
    #
    # Issue #1101 (Inv 68) — cross-check every parsed `#N` against
    # `gh issue view` and keep ONLY currently-OPEN issues. GitHub's closing
    # grammar treats `Fix #N` as a closing keyword, so a PR body enumerating
    # `Fix #1 / Fix #2 / Fix #3` would otherwise record #1/#2/#3 (the trap that
    # produced closed_issues=[1,2,3,1096] for #1100). Dropping non-open numbers
    # keeps the recorded set — and the loop bookkeeping derived from it — from
    # ever wrongly marking an unrelated issue closed. Dropped refs are logged
    # (in `_filter_open_issues`), never acted on.
    title = _pr_field(pr, "title", ".title")
    body = _pr_field(pr, "body", ".body")
    result["merge_sha"] = _pr_field(pr, "mergeCommit", ".mergeCommit.oid")
    result["closed_issues"] = _filter_open_issues(_parse_close_refs(title, body))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Squash-merge each PR in <pr-list> (comma-separated) "
                    "after delegating to safety-check.py. Refuses to merge "
                    "PRs whose base is not the sole integration target `main` "
                    "(Inv 61). Emits per-PR result JSON "
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
