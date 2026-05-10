#!/bin/bash
# check-symlinks-resolve.sh — assert every symlink under .claude/ resolves to an
# existing file or directory (no dangling symlinks).
#
# Usage: check-symlinks-resolve.sh [repo-root]
# Exit:  0 all symlinks resolve (or none found); 1 dangling symlinks found.

set -u

REPO_ROOT="${1:-${RABBIT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}}"

[ -z "$REPO_ROOT" ] && { echo "ERROR: cannot determine repo root" >&2; exit 2; }
[ ! -d "$REPO_ROOT/.claude" ] && { echo "OK: no .claude/ at $REPO_ROOT (vacuous)"; exit 0; }

# Use a temp file to track failure across the while-loop subshell
tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

find "$REPO_ROOT/.claude" -maxdepth 3 -type l | while read -r link; do
  target="$(readlink -f "$link" 2>/dev/null)"
  if [ -z "$target" ] || [ ! -e "$target" ]; then
    echo "DANGLING: $link" >&2
    echo "1" >> "$tmpfile"
  fi
done

if [ -s "$tmpfile" ]; then
  echo "FAIL: dangling symlinks found under $REPO_ROOT/.claude" >&2
  exit 1
fi

echo "OK: all symlinks under .claude/ resolve"
exit 0
