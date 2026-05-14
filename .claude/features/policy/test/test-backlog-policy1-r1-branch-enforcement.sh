#!/usr/bin/env bash
# test-backlog-policy1-r1-branch-enforcement.sh — Verifies R1 content is NOT in workflow-rules.md
# after archival. workflow-rules.md now contains only Section 4.
set -euo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$FEATURE_DIR/workflow-rules.md"

PASS=0
FAIL=0

check_phrase_absent() {
  local phrase="$1"
  if ! grep -q "$phrase" "$FILE"; then
    echo "PASS: '$phrase' correctly absent from workflow-rules.md (archived)"
    PASS=$((PASS + 1))
  else
    echo "FAIL: '$phrase' found in workflow-rules.md (should have been archived out)" >&2
    FAIL=$((FAIL + 1))
  fi
}

# R1 content was removed during archival — confirm it is gone
check_phrase_absent "session-init"
check_phrase_absent "never commit directly to main"
check_phrase_absent "R1"

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL test(s) failed" >&2
  exit 1
fi
echo "ALL TESTS PASSED"
