#!/usr/bin/env bash
# test-backlog001-r3-e2e.sh — Verifies R3 in workflow-rules.md mandates full E2E chain coverage.
# Spec invariant 4: R3 must explicitly require tests to exercise the full chain from
# user-facing entry point through to final state change, not just individual script behavior.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$FEATURE_DIR/workflow-rules.md"

PASS=0
FAIL=0

check_phrase() {
  local phrase="$1"
  if grep -q "$phrase" "$FILE"; then
    echo "PASS: '$phrase' found in workflow-rules.md"
    PASS=$((PASS + 1))
  else
    echo "FAIL: '$phrase' NOT found in workflow-rules.md" >&2
    FAIL=$((FAIL + 1))
  fi
}

# t1: R3 mentions full chain coverage (entry point through final state change)
check_phrase "full chain"

# t2: R3 mentions user-facing entry point
check_phrase "entry point"

# t3: R3 mentions final state change
check_phrase "final state change"

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL test(s) failed" >&2
  exit 1
fi
echo "ALL TESTS PASSED"
