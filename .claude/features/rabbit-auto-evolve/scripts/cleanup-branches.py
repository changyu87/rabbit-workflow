#!/usr/bin/env python3
"""cleanup-branches.py — delete merged-PR head branches after safety-check.

Usage:
  cleanup-branches.py <pr-list>

Where <pr-list> is a comma-separated list of merged PR numbers.

Per rabbit-auto-evolve spec.md Inv 6, for each PR this script:
  1. Derives the head branch via `gh pr view <#> --json headRefName -q .headRefName`.
  2. If the head does NOT match ^feat/.+ (or is 'dev', 'main', or starts
     with 'release/'), emits a stderr warning and records
     {pr, branch, status:"skipped", reason:"non-feat-branch"}. No deletion
     command is invoked — this local refusal is defense-in-depth above
     safety-check.py.
  3. Otherwise invokes `safety-check.py <pr#> --phase cleanup`. If non-zero,
     records {pr, branch, status:"skipped", reason:"safety-check-failed"}.
  4. Otherwise calls `git branch -D <branch>` (best-effort; non-zero exit
     acceptable — local branch may legitimately not exist) and
     `git push origin --delete <branch>`. On success records
     {pr, branch, status:"deleted"}; on `git push --delete` failure records
     {pr, branch, status:"failed"}.

The aggregated per-PR result list is emitted as JSON on stdout. The script
exits 0 except on argparse / unexpected error.

The sibling `safety-check.py` is resolved via RABBIT_AUTO_EVOLVE_SCRIPT_DIR
when set; otherwise via this script's own dirname (mirrors merge-prs.py).

Version: 1.0.0
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


FEAT_RE = re.compile(r"^feat/.+")


def _script_dir():
    return os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
                          os.path.dirname(os.path.abspath(__file__)))


def _head_ref(pr):
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr),
         "--json", "headRefName", "-q", ".headRefName"],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr


def _safety_check(pr):
    safety = os.path.join(_script_dir(), "safety-check.py")
    return subprocess.run(
        [sys.executable, safety, str(pr), "--phase", "cleanup"],
        capture_output=True, text=True,
    )


def _is_feat_branch(head):
    if head in ("dev", "main"):
        return False
    if head.startswith("release/"):
        return False
    return bool(FEAT_RE.match(head))


def process(pr):
    rc, head, stderr = _head_ref(pr)
    if rc != 0:
        sys.stderr.write(
            f"cleanup-branches: gh pr view #{pr} failed: {stderr.strip()}\n"
        )
        return {"pr": pr, "branch": None, "status": "skipped",
                "reason": "gh-view-failed"}

    if not _is_feat_branch(head):
        sys.stderr.write(
            f"cleanup-branches: refusing to delete non-feat branch "
            f"{head!r} for PR #{pr}\n"
        )
        return {"pr": pr, "branch": head, "status": "skipped",
                "reason": "non-feat-branch"}

    sc = _safety_check(pr)
    if sc.returncode != 0:
        return {"pr": pr, "branch": head, "status": "skipped",
                "reason": "safety-check-failed"}

    # Best-effort local branch -D; non-zero acceptable.
    subprocess.run(
        ["git", "branch", "-D", head],
        capture_output=True, text=True,
    )

    push = subprocess.run(
        ["git", "push", "origin", "--delete", head],
        capture_output=True, text=True,
    )
    if push.returncode != 0:
        return {"pr": pr, "branch": head, "status": "failed",
                "reason": f"push-delete-failed: {push.stderr.strip()}"}

    return {"pr": pr, "branch": head, "status": "deleted"}


def main():
    parser = argparse.ArgumentParser(
        description="Delete the head branch (local + origin) for each merged "
                    "PR in <pr-list> (comma-separated). Refuses to delete "
                    "branches not matching ^feat/.+. Emits per-PR result JSON "
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
