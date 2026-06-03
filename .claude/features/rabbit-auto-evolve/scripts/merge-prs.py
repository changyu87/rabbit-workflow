#!/usr/bin/env python3
"""merge-prs.py — squash-merge a list of PRs after delegating to safety-check.py.

Usage:
  merge-prs.py <pr-list>

Where <pr-list> is a comma-separated list of PR numbers.

Per rabbit-auto-evolve spec.md Inv 6, for each PR this script:
  1. Verifies the PR base via `gh pr view <#> --json baseRefName -q .baseRefName`.
     If base != 'dev' it records {pr, status:"skipped", reason:"base-not-dev"}
     and continues. The local `base != dev` check is defense-in-depth above
     safety-check.py — `gh pr merge` is NEVER invoked when base is not dev.
  2. Invokes `safety-check.py <pr#> --phase merge`. If it exits non-zero,
     records {pr, status:"skipped", reason:"safety-check-failed"}.
  3. Otherwise calls `gh pr merge <#> --squash --auto`. On success records
     {pr, status:"merged"}; on failure records
     {pr, status:"failed", reason:"gh-merge-failed: <stderr>"}.
  4. After a successful merge, parses the merged PR body for
     `Fixes #N` / `Closes #N` / `Resolves #N` references (case-insensitive)
     and explicitly closes each referenced issue via
     `item-status.py close <N> --reason completed --comment "...<sha>..."`.
     GitHub's native auto-close only fires for default-branch (`main`)
     merges; auto-evolve PRs always target `dev`, so without this step
     referenced issues would stay open indefinitely. Successfully-closed
     issue numbers are recorded under `closed_issues`; issues whose close
     command failed are recorded under `close_failed` and a warning is
     written to stderr — a close failure never fails the merge.

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

Version: 1.1.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import re
import subprocess
import sys

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


def _gh_merge(pr):
    return subprocess.run(
        ["gh", "pr", "merge", str(pr), "--squash", "--auto"],
        capture_output=True, text=True,
    )


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


def _parse_close_refs(body):
    """Return the sorted, de-duplicated list of issue numbers referenced by a
    closing keyword (Fixes/Closes/Resolves #N) in the PR body."""
    nums = {int(m) for m in _CLOSE_REF_RE.findall(body or "")}
    return sorted(nums)


def _item_status_close(num, sha):
    """Invoke item-status.py close on `num`. Returns the CompletedProcess.
    Idempotent against already-closed issues."""
    item_status = os.path.join(_issue_script_dir(), "item-status.py")
    comment = f"TDD cycle complete in {sha}" if sha else "TDD cycle complete"
    return subprocess.run(
        [sys.executable, item_status, "close", str(num),
         "--reason", "completed", "--comment", comment],
        capture_output=True, text=True,
    )


def _close_referenced_issues(pr, result):
    """After a successful merge, close every issue referenced by a closing
    keyword in the PR body. Mutates `result` in place, adding `closed_issues`
    and `close_failed`. A close failure never fails the merge."""
    body = _pr_field(pr, "body", ".body")
    sha = _pr_field(pr, "mergeCommit", ".mergeCommit.oid")
    refs = _parse_close_refs(body)
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
    if base != "dev":
        return {"pr": pr, "status": "skipped", "reason": "base-not-dev"}

    sc = _safety_check(pr)
    if sc.returncode != 0:
        return {"pr": pr, "status": "skipped",
                "reason": "safety-check-failed"}

    merge = _gh_merge(pr)
    if merge.returncode != 0:
        return {"pr": pr, "status": "failed",
                "reason": f"gh-merge-failed: {merge.stderr.strip()}"}

    result = {"pr": pr, "status": "merged"}
    _close_referenced_issues(pr, result)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Squash-merge each PR in <pr-list> (comma-separated) "
                    "after delegating to safety-check.py. Refuses to merge "
                    "PRs whose base is not 'dev'. Emits per-PR result JSON "
                    "array on stdout; always exit 0 except argparse error."
    )
    parser.add_argument("pr_list",
                        help="comma-separated list of PR numbers, e.g. '12,34'")
    args = parser.parse_args()

    try:
        prs = [int(s.strip()) for s in args.pr_list.split(",") if s.strip()]
    except ValueError as e:
        parser.error(f"invalid pr_list: {e}")

    results = [process(pr) for pr in prs]
    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
