#!/bin/bash
# test-backlog006.sh — Verifies workflow-rules.md contains only Section 4 after archival.
set -u

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW_RULES="$FEATURE_DIR/workflow-rules.md"
PASS=0
FAIL=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected="$3"  # "pass" or "fail"

    if eval "$test_command"; then
        result="pass"
    else
        result="fail"
    fi

    if [ "$result" = "$expected" ]; then
        echo "PASS: $test_name"
        ((PASS++))
    else
        echo "FAIL: $test_name (expected $expected, got $result)"
        ((FAIL++))
    fi
}

echo "Testing workflow-rules.md archival: only Section 4 remains"
echo "==========================================================="

# t1: workflow-rules.md contains '## 4. Token/compliance tradeoff'
run_test "t1: Contains '## 4. Token/compliance tradeoff'" \
    "grep -q '## 4\\. Token/compliance tradeoff is the user' '$WORKFLOW_RULES'" \
    "pass"

# t2: workflow-rules.md does NOT contain '## 1. Subagent-driven'
run_test "t2: Does NOT contain '## 1. Subagent-driven by construction'" \
    "grep -q '## 1\\. Subagent-driven by construction' '$WORKFLOW_RULES'" \
    "fail"

# t3: workflow-rules.md does NOT contain '## 2. Main Session Is a Dispatcher'
run_test "t3: Does NOT contain '## 2. Main Session Is a Dispatcher'" \
    "grep -q '## 2\\. Main Session Is a Dispatcher' '$WORKFLOW_RULES'" \
    "fail"

# t4: workflow-rules.md does NOT contain '## 3. Full TDD'
run_test "t4: Does NOT contain '## 3. Full TDD on every feature touch'" \
    "grep -q '## 3\\. Full TDD on every feature touch' '$WORKFLOW_RULES'" \
    "fail"

# t5: workflow-rules.md does NOT contain '## 5. Hard rules index'
run_test "t5: Does NOT contain '## 5. Hard rules index'" \
    "grep -q '## 5\\. Hard rules index' '$WORKFLOW_RULES'" \
    "fail"

# t6: workflow-rules.md does NOT contain '## 6. Cross-component handoffs'
run_test "t6: Does NOT contain '## 6. Cross-component handoffs'" \
    "grep -q '## 6\\. Cross-component handoffs' '$WORKFLOW_RULES'" \
    "fail"

echo ""
echo "==========================================================="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "==========================================================="

if [ $FAIL -eq 0 ]; then
    exit 0
else
    exit 1
fi
