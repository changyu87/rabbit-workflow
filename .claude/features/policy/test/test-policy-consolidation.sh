#!/usr/bin/env bash
# test-policy-consolidation.sh
# After archival: workflow-rules.md contains only Section 4.
# Asserts removed sections are gone; Section 4 content is intact; no stale prose.
set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
WF="$REPO_ROOT/.claude/features/policy/workflow-rules.md"
FAILURES=0

ok()   { echo "  PASS t$1: $2"; }
fail() { echo "  FAIL t$1: $2"; FAILURES=$((FAILURES + 1)); }

echo "test-policy-consolidation.sh"
echo ""

# t1: no 'Exception' keyword (capital E)
if ! grep -q 'Exception' "$WF"; then
    ok 1 "workflow-rules.md contains no 'Exception' clause"
else
    fail 1 "workflow-rules.md still contains 'Exception' — remove exception prose"
fi

# t2: no 'Exceptions' keyword (plural)
if ! grep -q 'Exceptions' "$WF"; then
    ok 2 "workflow-rules.md contains no 'Exceptions' block"
else
    fail 2 "workflow-rules.md still contains 'Exceptions' block — remove it"
fi

# t3: no 'enforced by scope-guard'
if ! grep -q 'enforced by scope-guard' "$WF"; then
    ok 3 "workflow-rules.md contains no 'enforced by scope-guard' reference"
else
    fail 3 "workflow-rules.md still references scope-guard enforcement — remove it"
fi

# t4: no script paths (check-no-main-edits.sh is the canary)
if ! grep -q 'check-no-main-edits' "$WF"; then
    ok 4 "workflow-rules.md contains no script paths"
else
    fail 4 "workflow-rules.md still contains script paths — remove them"
fi

# t5: Section 4 (Token/compliance) present
if grep -q '## 4\. Token/compliance tradeoff is the user' "$WF"; then
    ok 5 "Section 4 (Token/compliance tradeoff) present"
else
    fail 5 "Section 4 missing from workflow-rules.md"
fi

# t6: 'Subagent-driven by construction' section removed
if ! grep -q '## 1\. Subagent-driven by construction' "$WF"; then
    ok 6 "'Subagent-driven by construction' section correctly absent (archived)"
else
    fail 6 "'Subagent-driven by construction' section still present — should be archived"
fi

# t7: 'Full TDD on every feature touch' section removed
if ! grep -q '## 3\. Full TDD on every feature touch' "$WF"; then
    ok 7 "'Full TDD on every feature touch' section correctly absent (archived)"
else
    fail 7 "'Full TDD on every feature touch' section still present — should be archived"
fi

# t8: Hard rules index removed
if ! grep -q '## 5\. Hard rules index' "$WF"; then
    ok 8 "'Hard rules index' section correctly absent (archived)"
else
    fail 8 "'Hard rules index' section still present — should be archived"
fi

echo ""
echo "Results: $((8 - FAILURES)) passed, $FAILURES failed"
if [ "$FAILURES" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0
else echo "$FAILURES TEST(S) FAILED"; exit 1
fi
