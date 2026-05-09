#!/bin/bash
# test-policy-block.sh — verify policy-block.sh output is correct.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$FEATURE_DIR/scripts/policy-block.sh"
FAIL=0

OUTPUT="$("$SCRIPT" 2>&1)"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: policy-block.sh exited with code $EXIT_CODE" >&2
  FAIL=1
fi

check_contains() {
  local label="$1"
  local pattern="$2"
  if ! echo "$OUTPUT" | grep -qF "$pattern"; then
    echo "FAIL: output does not contain '$pattern' (check: $label)" >&2
    FAIL=1
  fi
}

check_contains "sentinel line" "RABBIT-POLICY-BLOCK-v1"
check_contains "banner" "MANDATORY POLICY"
check_contains "philosophy.md section header" "philosophy.md"
check_contains "workflow-rules.md section header" "workflow-rules.md"

if [ $FAIL -ne 0 ]; then
  echo "test-policy-block: FAIL" >&2
  exit 1
fi

echo "test-policy-block: all checks passed."
