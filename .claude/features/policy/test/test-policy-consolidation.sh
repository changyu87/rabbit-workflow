#!/usr/bin/env bash
# test-policy-consolidation.sh
# Asserts workflow-rules.md contains no exception prose or script-path refs.
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
    fail 4 "workflow-rules.md still contains script paths in R1–R9 — compress to one-liners"
fi

# t5: R1 present as one-liner bullet
if grep -q '^\- \*\*R1\*\*' "$WF"; then
    ok 5 "R1 present as one-liner bullet"
else
    fail 5 "R1 not found as one-liner bullet '- **R1**'"
fi

# t6: R9 present as one-liner bullet
if grep -q '^\- \*\*R9\*\*' "$WF"; then
    ok 6 "R9 present as one-liner bullet"
else
    fail 6 "R9 not found as one-liner bullet '- **R9**'"
fi

# t7: 'Subagent-driven by construction' section still exists
if grep -q '## Subagent-driven by construction' "$WF"; then
    ok 7 "'Subagent-driven by construction' section present"
else
    fail 7 "'Subagent-driven by construction' section missing"
fi

# t8: 'Full TDD on every feature touch' section still exists
if grep -q '## Full TDD on every feature touch' "$WF"; then
    ok 8 "'Full TDD on every feature touch' section present"
else
    fail 8 "'Full TDD on every feature touch' section missing"
fi

echo ""
echo "Results: $((8 - FAILURES)) passed, $FAILURES failed"
if [ "$FAILURES" -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0
else echo "$FAILURES TEST(S) FAILED"; exit 1
fi
