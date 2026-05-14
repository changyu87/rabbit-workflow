#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=0; FAIL=0
for t in "$SCRIPT_DIR"/test-*.sh; do
  [ -f "$t" ] || continue
  if bash "$t"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi
done
echo "Total: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
