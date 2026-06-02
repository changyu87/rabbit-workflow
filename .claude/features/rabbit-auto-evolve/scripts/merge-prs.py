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

The aggregated per-PR result list is emitted as JSON on stdout. The script
exits 0 except on argparse / unexpected error — partial-outcome reporting
is the caller's responsibility.

The sibling `safety-check.py` is resolved via the
RABBIT_AUTO_EVOLVE_SCRIPT_DIR env var when set; otherwise it falls back to
this script's own dirname. This allows tests to inject a shim without
touching the real safety-check.py.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys


def _script_dir():
    return os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
                          os.path.dirname(os.path.abspath(__file__)))


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
    return {"pr": pr, "status": "merged"}


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
