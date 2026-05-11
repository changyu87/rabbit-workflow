#!/usr/bin/env bash
# test-policy-restructure.sh — verify post-restructure state of policy markdown files
# R3-compliant: non-interactive, full-stack, no read/select constructs

set -u

POLICY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CODING="$POLICY_DIR/coding-rules.md"
SPEC="$POLICY_DIR/spec-rules.md"
WORKFLOW="$POLICY_DIR/workflow-rules.md"

pass=0
fail=0

check() {
    local id="$1"
    local description="$2"
    local result="$3"   # 0 = assertion holds, non-zero = fails
    if [ "$result" -eq 0 ]; then
        echo "PASS t${id}: ${description}"
        pass=$((pass + 1))
    else
        echo "FAIL t${id}: ${description}"
        fail=$((fail + 1))
    fi
}

# ── coding-rules.md ──────────────────────────────────────────────────────────

# t1: does NOT contain '## Code-Editing Discipline'
grep -qF '## Code-Editing Discipline' "$CODING" && result=1 || result=0
check 1 "coding-rules.md does NOT contain '## Code-Editing Discipline'" "$result"

# t2: does NOT contain '### 1.' (H3 rules promoted to H2)
grep -qE '^### 1\.' "$CODING" && result=1 || result=0
check 2 "coding-rules.md does NOT contain '### 1.' (H3 promoted to H2)" "$result"

# t3: contains '## 1. Think Before Coding' (exact H2, not H3)
grep -qE '^## 1\. Think Before Coding' "$CODING" && result=0 || result=1
check 3 "coding-rules.md contains '## 1. Think Before Coding'" "$result"

# t4: contains '## 4. Goal-Driven Execution' (exact H2, not H3)
grep -qE '^## 4\. Goal-Driven Execution' "$CODING" && result=0 || result=1
check 4 "coding-rules.md contains '## 4. Goal-Driven Execution'" "$result"

# t5: does NOT contain '## 5.' or '### 5.' (rule 5 moved out)
grep -qE '^(##|###) 5\.' "$CODING" && result=1 || result=0
check 5 "coding-rules.md does NOT contain '## 5.' or '### 5.' (rule 5 moved out)" "$result"

# t6: contains 'Adapted from Andrej Karpathy' (attribution one-liner, no URL)
grep -qF 'Adapted from Andrej Karpathy' "$CODING" && result=0 || result=1
check 6 "coding-rules.md contains 'Adapted from Andrej Karpathy'" "$result"

# t7: the line(s) containing 'Karpathy' do NOT contain 'http'
karpathy_lines="$(grep 'Karpathy' "$CODING" 2>/dev/null || true)"
if [ -z "$karpathy_lines" ]; then
    # No Karpathy line at all — t6 already catches absence; treat t7 as fail too
    result=1
else
    echo "$karpathy_lines" | grep -q 'http' && result=1 || result=0
fi
check 7 "Karpathy attribution line(s) do NOT contain 'http'" "$result"

# ── spec-rules.md ─────────────────────────────────────────────────────────────

# t8: does NOT contain 'Part I'
grep -qF 'Part I' "$SPEC" && result=1 || result=0
check 8 "spec-rules.md does NOT contain 'Part I'" "$result"

# t9: does NOT contain '### 1.' (H3 rules promoted to H2)
grep -qE '^### 1\.' "$SPEC" && result=1 || result=0
check 9 "spec-rules.md does NOT contain '### 1.' (H3 promoted to H2)" "$result"

# t10: contains '## 1. Tool-Choice Tier' (exact H2, not H3)
grep -qE '^## 1\. Tool-Choice Tier' "$SPEC" && result=0 || result=1
check 10 "spec-rules.md contains '## 1. Tool-Choice Tier'" "$result"

# t11: contains '## 3. Lifecycle and Ownership' (exact H2, not H3)
grep -qE '^## 3\. Lifecycle and Ownership' "$SPEC" && result=0 || result=1
check 11 "spec-rules.md contains '## 3. Lifecycle and Ownership'" "$result"

# ── workflow-rules.md ─────────────────────────────────────────────────────────

# t12: does NOT contain 'Section 1' (Section N prefix dropped)
grep -qF 'Section 1' "$WORKFLOW" && result=1 || result=0
check 12 "workflow-rules.md does NOT contain 'Section 1'" "$result"

# t13: contains '## Subagent-driven by construction' (exact H2)
grep -qE '^## Subagent-driven by construction' "$WORKFLOW" && result=0 || result=1
check 13 "workflow-rules.md contains '## Subagent-driven by construction'" "$result"

# t14: contains '## Main Session Is a Dispatcher, Not an Implementer' (exact H2)
grep -qE '^## Main Session Is a Dispatcher, Not an Implementer' "$WORKFLOW" && result=0 || result=1
check 14 "workflow-rules.md contains '## Main Session Is a Dispatcher, Not an Implementer'" "$result"

# t15: contains '## Hard rules index' (exact H2)
grep -qE '^## Hard rules index' "$WORKFLOW" && result=0 || result=1
check 15 "workflow-rules.md contains '## Hard rules index'" "$result"

# ── summary ──────────────────────────────────────────────────────────────────

echo ""
echo "Results: ${pass} passed, ${fail} failed"

if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
