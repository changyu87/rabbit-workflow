#!/usr/bin/env bash
# make-readonly.sh — remove write permission from archive/ and test/.
# Run once after git clone. Unlock with make-writable.sh when needed.
# Honors ARCHIVE_DIR and TEST_DIR env vars for testing.
set -euo pipefail
ARCHIVE_DIR="${ARCHIVE_DIR:-archive}"
TEST_DIR="${TEST_DIR:-test}"
[ -d "$ARCHIVE_DIR" ] && chmod -R a-w "$ARCHIVE_DIR" && echo "read-only: $ARCHIVE_DIR/"
[ -d "$TEST_DIR" ]    && chmod -R a-w "$TEST_DIR"    && echo "read-only: $TEST_DIR/"
