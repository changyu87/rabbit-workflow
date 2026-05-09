#!/usr/bin/env bash
# make-writable.sh — restore write permission to archive/ and test/.
# Honors ARCHIVE_DIR and TEST_DIR env vars for testing.
set -euo pipefail
ARCHIVE_DIR="${ARCHIVE_DIR:-archive}"
TEST_DIR="${TEST_DIR:-test}"
[ -d "$ARCHIVE_DIR" ] && chmod -R u+w "$ARCHIVE_DIR" && echo "writable: $ARCHIVE_DIR/"
[ -d "$TEST_DIR" ]    && chmod -R u+w "$TEST_DIR"    && echo "writable: $TEST_DIR/"
