#!/usr/bin/env bash
# Tests for dispatch-spec-update.sh
set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/contract/scripts/dispatch-spec-update.sh"

PASS=0; FAIL=0
ok() { echo "  PASS $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

echo "test-dispatch-spec-update.sh"

# t1: script exists and is executable
if [ -f "$SCRIPT" ] && [ -x "$SCRIPT" ]; then
  ok "t1: dispatch-spec-update.sh exists and is executable"
else
  ko "t1: dispatch-spec-update.sh missing or not executable at $SCRIPT"
fi

# t2: no args → exit 2
t2_rc=0
"$SCRIPT" 2>/dev/null || t2_rc=$?
if [ "$t2_rc" = "2" ]; then
  ok "t2: no args exits 2"
else
  ko "t2: expected exit 2 on no args, got $t2_rc"
fi

# t3: unknown feature → exit 1
t3_rc=0
"$SCRIPT" nonexistent-feature-xyz "some change" 2>/dev/null || t3_rc=$?
if [ "$t3_rc" = "1" ]; then
  ok "t3: unknown feature exits 1"
else
  ko "t3: expected exit 1 for unknown feature, got $t3_rc"
fi

# t4: output starts with RABBIT-POLICY-BLOCK-v1 sentinel for known feature
t4_out=""
t4_out="$("$SCRIPT" rabbit-cage "test change description" 2>/dev/null)" || true
if echo "$t4_out" | head -1 | grep -q "RABBIT-POLICY-BLOCK-v1"; then
  ok "t4: output starts with RABBIT-POLICY-BLOCK-v1 sentinel"
else
  ko "t4: sentinel missing; first line: '$(echo "$t4_out" | head -1)'"
fi

# t5: output contains spec content (spot-check: feature name present in spec)
if echo "$t4_out" | grep -q "rabbit-cage"; then
  ok "t5: output contains spec content (feature name present)"
else
  ko "t5: spec content not injected into prompt"
fi

# t6: output contains the change description
if echo "$t4_out" | grep -q "test change description"; then
  ok "t6: output contains the change description"
else
  ko "t6: change description not in prompt output"
fi

# t7: output contains SCOPE declaration for the feature
if echo "$t4_out" | grep -q "SCOPE: rabbit-cage"; then
  ok "t7: output contains SCOPE: rabbit-cage"
else
  ko "t7: SCOPE declaration missing"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
