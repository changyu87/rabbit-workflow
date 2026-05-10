#!/bin/bash
# check-imports-resolve.sh — assert every @<path> import and .claude/features/<name>
# path reference in docs/ .md files resolves to an existing filesystem path.
#
# Usage: check-imports-resolve.sh <feature-dir>
# Exit:  0 all paths resolve (or no docs/); 1 one or more missing paths.

set -u

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"

dir="${1:-}"
[ -z "$dir" ] && { echo "usage: check-imports-resolve.sh <feature-dir>" >&2; exit 2; }

docsdir="$dir/docs"
[ ! -d "$docsdir" ] && { echo "OK: no docs/ in $dir (vacuous)"; exit 0; }

fail=0

while IFS= read -r file; do
  # Extract @./ imports: @./path/to/something
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    # Skip template placeholders
    case "$path" in *"{{"*) continue ;; esac
    # Skip paths inside archive/ directories
    case "$file" in */archive/*) continue ;; esac
    if [ ! -e "$REPO_ROOT/$path" ]; then
      echo "MISSING: $path (in $file)" >&2
      fail=1
    fi
  done < <(grep -oE '@\./[^[:space:]]+' "$file" | sed 's/^@\.\///')

  # Extract .claude/features/<name> paths
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    # Skip template placeholders
    case "$path" in *"{{"*) continue ;; esac
    # Skip paths inside archive/ directories
    case "$file" in */archive/*) continue ;; esac
    if [ ! -e "$REPO_ROOT/$path" ]; then
      echo "MISSING: $path (in $file)" >&2
      fail=1
    fi
  done < <(grep -oE '\.claude/features/[a-z][a-z0-9-]+(/[^[:space:])\]'"'"']+)?' "$file")

done < <(find "$docsdir" -type f -name '*.md')

if [ "$fail" -ne 0 ]; then
  echo "FAIL: one or more import/path references are missing" >&2
  exit 1
fi

echo "OK: all import and feature path references resolve"
exit 0
