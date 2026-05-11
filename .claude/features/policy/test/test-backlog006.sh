#!/bin/bash

set -u

WORKFLOW_RULES="/home/cyxu/workflow-dev/rabbit-sprint/.claude/features/policy/workflow-rules.md"
PASS=0
FAIL=0

# Helper function to run a test
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
        echo "✓ $test_name"
        ((PASS++))
    else
        echo "✗ $test_name (expected $expected, got $result)"
        ((FAIL++))
    fi
}

echo "Testing BACKLOG-006: workflow-rules.md section numbering"
echo "=========================================================="

# t1: workflow-rules.md contains '## 1. Subagent-driven by construction'
run_test "t1: Contains '## 1. Subagent-driven by construction'" \
    "grep -q '## 1\\. Subagent-driven by construction' '$WORKFLOW_RULES'" \
    "pass"

# t2: workflow-rules.md contains '## 2. Main Session Is a Dispatcher'
run_test "t2: Contains '## 2. Main Session Is a Dispatcher'" \
    "grep -q '## 2\\. Main Session Is a Dispatcher' '$WORKFLOW_RULES'" \
    "pass"

# t3: workflow-rules.md contains '## 3. Full TDD on every feature touch'
run_test "t3: Contains '## 3. Full TDD on every feature touch'" \
    "grep -q '## 3\\. Full TDD on every feature touch' '$WORKFLOW_RULES'" \
    "pass"

# t4: workflow-rules.md contains '## 4. Token/compliance tradeoff'
run_test "t4: Contains '## 4. Token/compliance tradeoff'" \
    "grep -q '## 4\\. Token/compliance tradeoff is the user' '$WORKFLOW_RULES'" \
    "pass"

# t5: workflow-rules.md contains '## 5. Hard rules index'
run_test "t5: Contains '## 5. Hard rules index'" \
    "grep -q '## 5\\. Hard rules index' '$WORKFLOW_RULES'" \
    "pass"

# t6: workflow-rules.md contains '## 6. Cross-component handoffs'
run_test "t6: Contains '## 6. Cross-component handoffs'" \
    "grep -q '## 6\\. Cross-component handoffs' '$WORKFLOW_RULES'" \
    "pass"

# t7: workflow-rules.md does NOT contain '## Subagent-driven' (unnumbered form gone)
run_test "t7: Does NOT contain '## Subagent-driven' (unnumbered)" \
    "grep -q '## Subagent-driven' '$WORKFLOW_RULES'" \
    "fail"

# t8: workflow-rules.md does NOT contain '## Full TDD' (unnumbered form gone)
run_test "t8: Does NOT contain '## Full TDD' (unnumbered)" \
    "grep -q '## Full TDD' '$WORKFLOW_RULES'" \
    "fail"

echo ""
echo "=========================================================="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "=========================================================="

if [ $FAIL -eq 0 ]; then
    exit 0
else
    exit 1
fi
