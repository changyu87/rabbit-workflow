#!/usr/bin/env bash
# make-readonly.sh — remove owner write permission from archive/ and test/.
# Run once after git clone. Unlock with make-writable.sh when needed.
# Uses find to avoid following symlinks to external targets.
# Honors ARCHIVE_DIR and TEST_DIR env vars for testing.
set -euo pipefail
ARCHIVE_DIR="${ARCHIVE_DIR:-archive}"
TEST_DIR="${TEST_DIR:-test}"
_lock() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  find "$dir" ! -type l -exec chmod u-w {} + || { echo "ERROR: chmod failed on $dir/" >&2; exit 1; }
  echo "read-only: $dir/"
}
_lock "$ARCHIVE_DIR"
_lock "$TEST_DIR"
