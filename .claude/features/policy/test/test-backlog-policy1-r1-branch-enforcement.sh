#!/usr/bin/env bash
# test-backlog-policy1-r1-branch-enforcement.sh — Verifies R1 in workflow-rules.md contains
# explicit branch-enforcement language.
# Spec invariant 5: R1 must explicitly state:
#   (a) session-init hook automatically creates a feature branch when started on main
#   (b) all commits must land on a feature branch, never directly on main
#   (c) PR/merge step is the only path back to main
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

# t1: R1 mentions session-init hook creating a feature branch when on main
check_phrase "session-init"

# t2: R1 states commits must land on a feature branch (never on main)
check_phrase "never commit directly to main"

# t3: R1 states PR/merge is the only path to main
check_phrase "PR"

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL test(s) failed" >&2
  exit 1
fi
echo "ALL TESTS PASSED"
