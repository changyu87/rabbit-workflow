#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0; FAIL=0
run_suite() {
  local suite="$1"
  if bash "$DIR/$suite"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi
}
run_suite "test-scope-guard-symlink.sh"
echo ""
echo "suites: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
