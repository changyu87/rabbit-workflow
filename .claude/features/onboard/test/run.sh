#!/bin/bash
# run.sh — end-to-end runner for onboard feature tests.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FAIL=0
for t in "$SCRIPT_DIR"/test-*.sh; do
  echo "=== $(basename "$t") ==="
  bash "$t" || FAIL=$((FAIL+1))
  echo
done
if [ "$FAIL" -eq 0 ]; then
  echo "ALL PASS"
  exit 0
fi
echo "FAILED: $FAIL test file(s)"
exit 1
