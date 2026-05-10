#!/bin/bash
# test-sentinel-check.sh — tests for check-sentinel.sh.
# Non-interactive. Exits non-zero on failure.

set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK="$FEATURE_DIR/scripts/check-sentinel.sh"
CONTRACT_SCRIPTS="$FEATURE_DIR/../contract/scripts"

FAIL=0

check() {
  local label="$1"
  local expected_exit="$2"
  shift 2
  local actual_exit=0
  "$CHECK" "$@" >/dev/null 2>&1 || actual_exit=$?
  if [ "$actual_exit" -ne "$expected_exit" ]; then
    echo "FAIL [$label]: expected exit $expected_exit, got $actual_exit" >&2
    FAIL=1
  fi
}

# Test 1: file WITH sentinel -> exits 0.
TMP_WITH="$(mktemp)"
echo "RABBIT-POLICY-BLOCK-v1" > "$TMP_WITH"
check "file-with-sentinel" 0 "$TMP_WITH"
rm -f "$TMP_WITH"

# Test 2: file WITHOUT sentinel -> exits 1.
TMP_WITHOUT="$(mktemp)"
echo "no sentinel here" > "$TMP_WITHOUT"
check "file-without-sentinel" 1 "$TMP_WITHOUT"
rm -f "$TMP_WITHOUT"

# Test 3: dispatch-feature-edit.sh source contains sentinel -> exits 0.
DISPATCH="$CONTRACT_SCRIPTS/dispatch-feature-edit.sh"
if [ ! -f "$DISPATCH" ]; then
  echo "FAIL: dispatch-feature-edit.sh not found at $DISPATCH" >&2
  FAIL=1
else
  check "dispatch-feature-edit-has-sentinel" 0 "$DISPATCH"
fi

# Test 4: dispatch-feature-edit.sh source contains the literal sentinel string.
if [ -f "$DISPATCH" ]; then
  if ! grep -qF "RABBIT-POLICY-BLOCK-v1" "$DISPATCH"; then
    echo "FAIL: dispatch-feature-edit.sh does not contain literal RABBIT-POLICY-BLOCK-v1" >&2
    FAIL=1
  fi
fi

if [ $FAIL -ne 0 ]; then
  echo "test-sentinel-check: FAIL" >&2
  exit 1
fi

echo "test-sentinel-check: all checks passed."
