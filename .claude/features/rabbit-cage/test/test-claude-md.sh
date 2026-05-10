#!/usr/bin/env bash
# rabbit-cage CLAUDE.md @-import tests
# Tests that CLAUDE.md has the correct @-imports after migration.
# All tests must FAIL before implementation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

echo "test-claude-md.sh"

# t1: CLAUDE.md @-imports do NOT contain "philosophy.md" at .claude/ flat path
if ! grep -qE '@.*\.claude/philosophy\.md' "$CLAUDE_MD" 2>/dev/null; then
    ok 1 "CLAUDE.md does not @-import .claude/philosophy.md"
else
    fail_t 1 "CLAUDE.md still @-imports .claude/philosophy.md (stale flat path)"
fi

# t2: CLAUDE.md @-imports do NOT contain "work-guide.md"
if ! grep -qE '@.*work-guide\.md' "$CLAUDE_MD" 2>/dev/null; then
    ok 2 "CLAUDE.md does not @-import work-guide.md"
else
    fail_t 2 "CLAUDE.md still @-imports work-guide.md"
fi

# t3: CLAUDE.md contains inline policy start marker
if grep -q 'rabbit-policy-start' "$CLAUDE_MD" 2>/dev/null; then
    ok 3 "CLAUDE.md contains inline rabbit-policy-start marker"
else
    fail_t 3 "CLAUDE.md does not contain rabbit-policy-start marker (not yet generated)"
fi

# t4: CLAUDE.md contains verbatim policy content (spot-check: "Machine First")
if grep -q 'Machine First' "$CLAUDE_MD" 2>/dev/null; then
    ok 4 "CLAUDE.md contains verbatim policy content ('Machine First' present)"
else
    fail_t 4 "CLAUDE.md does not contain 'Machine First' — inline policy content missing"
fi

# t5: .claude/philosophy.md does NOT exist (removed as part of migration)
if [ ! -f "$REPO_ROOT/.claude/philosophy.md" ]; then
    ok 5 ".claude/philosophy.md does not exist (removed)"
else
    fail_t 5 ".claude/philosophy.md still exists (not yet removed)"
fi

# t6: .claude/work-guide.md does NOT exist
if [ ! -f "$REPO_ROOT/.claude/work-guide.md" ]; then
    ok 6 ".claude/work-guide.md does not exist (removed)"
else
    fail_t 6 ".claude/work-guide.md still exists (not yet removed)"
fi

# t7: CLAUDE.md contains "subagent-driven development"
if grep -q "subagent-driven development" "$CLAUDE_MD" 2>/dev/null; then
    ok 7 "CLAUDE.md contains 'subagent-driven development'"
else
    fail_t 7 "CLAUDE.md does not contain 'subagent-driven development' (not yet added)"
fi

# t8: CLAUDE.md does NOT contain "two source-of-truth" (old phrase should be gone)
if ! grep -q "two source-of-truth" "$CLAUDE_MD" 2>/dev/null; then
    ok 8 "CLAUDE.md does not contain old phrase 'two source-of-truth'"
else
    fail_t 8 "CLAUDE.md still contains old phrase 'two source-of-truth' (not yet removed)"
fi

# t9: test-backlog-e2e-tdd.sh IS registered in run.sh
RUN_SH="$REPO_ROOT/.claude/features/rabbit-cage/test/run.sh"
if grep -q "test-backlog-e2e-tdd.sh" "$RUN_SH" 2>/dev/null; then
    ok 9 "test-backlog-e2e-tdd.sh is registered in run.sh"
else
    fail_t 9 "test-backlog-e2e-tdd.sh is NOT registered in run.sh (not yet added)"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
