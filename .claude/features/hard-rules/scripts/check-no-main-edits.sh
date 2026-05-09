#!/bin/bash
# check-no-main-edits.sh — fail if the current git branch is main / master.
# Intended as a pre-commit / pre-PR guard for the rabbit workflow:
#   "Never work on main; every feature mutation must be on a new branch."
#
# Exit: 0 not on main; 1 on main (or master); 2 not in a git repo.

set -u

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: not a git repo" >&2
  exit 2
fi

# Get current branch name (handles detached HEAD too).
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then
  echo "ERROR: detached HEAD or unknown branch state" >&2
  exit 1
fi

case "$branch" in
  main|master|trunk|develop)
    echo "REJECTED: you are on '$branch'. Per branch-per-feature rule, every change goes on a new branch and through a PR." >&2
    exit 1
    ;;
  *)
    echo "OK: on '$branch' (not main)"
    exit 0
    ;;
esac
