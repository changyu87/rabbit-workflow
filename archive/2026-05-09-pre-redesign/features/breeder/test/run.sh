#!/bin/bash
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FAIL=0
for t in "$SCRIPT_DIR"/test-*.sh; do
  echo "=== $(basename "$t") ==="
  bash "$t" || FAIL=$((FAIL+1))
  echo
done
[ "$FAIL" -eq 0 ] && { echo "ALL PASS"; exit 0; }
echo "FAILED: $FAIL test file(s)"; exit 1
