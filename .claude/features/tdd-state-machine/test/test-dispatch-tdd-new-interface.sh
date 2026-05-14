#!/bin/bash
# test-dispatch-tdd-new-interface.sh
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# 1. --bug flag is rejected (removed in new interface)
"$SCRIPT" contract "test" --bug /tmp/fake 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "--bug flag rejected" || fail "--bug should be rejected"

# 2. --backlog flag is rejected
"$SCRIPT" contract "test" --backlog /tmp/fake 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "--backlog flag rejected" || fail "--backlog should be rejected"

# 3. --linked-item without --item-type is rejected
"$SCRIPT" contract "test" --linked-item /tmp/fake 2>/dev/null; code=$?
[ "$code" -ne 0 ] && ok "--linked-item without --item-type rejected" || fail "should reject missing --item-type"

# 4. valid basic invocation emits non-empty prompt
prompt=$("$SCRIPT" contract "fix the scope guard" 2>/dev/null)
[ -n "$prompt" ] && ok "basic invocation emits prompt" || fail "empty prompt"

# 5. prompt references tdd-report.json
echo "$prompt" | grep -q "tdd-report.json" && ok "prompt references tdd-report.json" || fail "prompt missing tdd-report.json"

# 6. prompt contains spec_compliance field in schema
echo "$prompt" | grep -q "spec_compliance" && ok "prompt contains spec_compliance" || fail "prompt missing spec_compliance"

# 7. prompt contains test_gap_analysis field
echo "$prompt" | grep -q "test_gap_analysis" && ok "prompt contains test_gap_analysis" || fail "prompt missing test_gap_analysis"

# 8. --linked-item --item-type bug is accepted
prompt2=$("$SCRIPT" contract "test" --linked-item /tmp/fake-bug --item-type bug 2>/dev/null)
[ -n "$prompt2" ] && ok "--linked-item --item-type bug accepted" || fail "--linked-item bug rejected"

# 9. prompt mentions inline spec-review (no nested Agent)
echo "$prompt" | grep -qi "inline\|spec.review\|spec-review" && ok "prompt mentions inline spec-review" || fail "prompt missing inline spec-review instruction"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
