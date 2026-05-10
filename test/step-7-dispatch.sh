#!/bin/bash
# step-7-dispatch.sh — integration test for Step 7 changes.
# Non-interactive. Exits non-zero on failure.

set -u

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"
FAIL=0

check() {
  local label="$1"
  local result="$2"
  if [ "$result" != "0" ]; then
    echo "FAIL: $label" >&2
    FAIL=1
  fi
}

# Test 1: dispatch-feature-edit.sh source does NOT contain [stub].
DISPATCH="$REPO_ROOT/.claude/features/contract/scripts/dispatch-feature-edit.sh"
if grep -qF "[stub]" "$DISPATCH"; then
  echo "FAIL: dispatch-feature-edit.sh still contains '[stub]'" >&2
  FAIL=1
else
  echo "PASS: no [stub] in dispatch-feature-edit.sh"
fi

# Test 2: .claude/agents/rabbit-breeder.md does NOT exist.
BREEDER="$REPO_ROOT/.claude/agents/rabbit-breeder.md"
if [ -f "$BREEDER" ]; then
  echo "FAIL: rabbit-breeder.md still exists at $BREEDER" >&2
  FAIL=1
else
  echo "PASS: rabbit-breeder.md absent from .claude/agents/"
fi

# Test 3: archive copy EXISTS.
ARCHIVED="$REPO_ROOT/archive/2026-05-09-pre-redesign/agents/rabbit-breeder.md"
if [ ! -f "$ARCHIVED" ]; then
  echo "FAIL: archived rabbit-breeder.md not found at $ARCHIVED" >&2
  FAIL=1
else
  echo "PASS: rabbit-breeder.md present in archive"
fi

# Test 4: check-sentinel.sh is executable.
SENTINEL_CHECK="$REPO_ROOT/.claude/features/hard-rules/scripts/check-sentinel.sh"
if [ ! -x "$SENTINEL_CHECK" ]; then
  echo "FAIL: check-sentinel.sh is not executable (or missing) at $SENTINEL_CHECK" >&2
  FAIL=1
else
  echo "PASS: check-sentinel.sh is executable"
fi

# Test 5: check-sentinel.sh passes on dispatch-feature-edit.sh.
if [ -x "$SENTINEL_CHECK" ] && [ -f "$DISPATCH" ]; then
  if ! "$SENTINEL_CHECK" "$DISPATCH" >/dev/null 2>&1; then
    echo "FAIL: check-sentinel.sh reported missing sentinel in dispatch-feature-edit.sh" >&2
    FAIL=1
  else
    echo "PASS: sentinel present in dispatch-feature-edit.sh"
  fi
fi

if [ $FAIL -ne 0 ]; then
  echo "step-7-dispatch: FAIL ($FAIL check(s) failed)" >&2
  exit 1
fi

echo "step-7-dispatch: ALL PASSED"
