#!/usr/bin/env python3
"""check-no-main-edits.py — fail if the current git branch is main / master.
Intended as a pre-commit / pre-PR guard for the rabbit workflow:
  "Never work on main; every feature mutation must be on a new branch."

Exit: 0 not on main; 1 on main (or master); 2 not in a git repo.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when branch enforcement is provided by a native CI check.
"""

import subprocess
import sys


def main():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("ERROR: not a git repo", file=sys.stderr)
            sys.exit(2)
    except FileNotFoundError:
        print("ERROR: git not found", file=sys.stderr)
        sys.exit(2)

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    branch = result.stdout.strip()

    if not branch or branch == "HEAD":
        print("ERROR: detached HEAD or unknown branch state", file=sys.stderr)
        sys.exit(1)

    if branch in ("main", "master", "trunk", "develop"):
        print(
            f"REJECTED: you are on '{branch}'. Per branch-per-feature rule, "
            "every change goes on a new branch and through a PR.",
            file=sys.stderr
        )
        sys.exit(1)

    print(f"OK: on '{branch}' (not main)")
    sys.exit(0)


if __name__ == "__main__":
    main()
