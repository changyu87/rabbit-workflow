#!/usr/bin/env bash
# make-writable.sh — restore owner write permission to archive/ and test/.
# Uses find to avoid following symlinks to external targets.
# Honors ARCHIVE_DIR and TEST_DIR env vars for testing.
set -euo pipefail
ARCHIVE_DIR="${ARCHIVE_DIR:-archive}"
TEST_DIR="${TEST_DIR:-test}"
_unlock() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  find "$dir" ! -type l -exec chmod u+w {} + || { echo "ERROR: chmod failed on $dir/" >&2; exit 1; }
  echo "writable: $dir/"
}
_unlock "$ARCHIVE_DIR"
_unlock "$TEST_DIR"
