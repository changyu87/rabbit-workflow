#!/bin/bash
# check-sentinel.sh — verify RABBIT-POLICY-BLOCK-v1 sentinel in dispatch scripts.
#
# Usage: check-sentinel.sh <file-or-dir>
#
# If given a file: checks that file for the sentinel string.
# If given a directory: recursively finds all .sh files and checks each.
# Exits 0 if all checked files contain the sentinel, 1 if any are missing it.

set -u

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "ERROR: usage: check-sentinel.sh <file-or-dir>" >&2
  exit 2
fi

SENTINEL="RABBIT-POLICY-BLOCK-v1"
FAILED=0

check_file() {
  local f="$1"
  if ! grep -q "$SENTINEL" "$f"; then
    echo "MISSING sentinel in: $f" >&2
    FAILED=1
  fi
}

if [ -f "$TARGET" ]; then
  check_file "$TARGET"
elif [ -d "$TARGET" ]; then
  while IFS= read -r f; do
    check_file "$f"
  done < <(find "$TARGET" -name "*.sh" -type f)
else
  echo "ERROR: not a file or directory: $TARGET" >&2
  exit 2
fi

exit $FAILED
