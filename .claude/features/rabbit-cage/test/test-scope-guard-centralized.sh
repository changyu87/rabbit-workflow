#!/usr/bin/env bash
# rabbit-cage: scope-guard centralized path allowlist tests
# Tests for:
#   t1: scope-guard.sh has path-based check for .claude/bugs/
#   t2: scope-guard.sh has path-based check for .claude/backlogs/
#   t3: run.sh does NOT contain test-backlog-e2e-tdd.sh
#   t4: test-claude-md.sh does NOT assert test-backlog-e2e-tdd.sh IS in run.sh
#
# All tests must FAIL before implementation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.sh"
RUN_SH="$REPO_ROOT/.claude/features/rabbit-cage/test/run.sh"
TEST_CLAUDE_MD="$REPO_ROOT/.claude/features/rabbit-cage/test/test-claude-md.sh"

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

echo "test-scope-guard-centralized.sh"

# t1: scope-guard.sh source contains a path-based check for .claude/bugs/
if grep -q 'bugs' "$SCOPE_GUARD" 2>/dev/null; then
    ok 1 "scope-guard.sh contains path-based check for .claude/bugs/"
else
    fail_t 1 "scope-guard.sh does NOT contain a path-based check for .claude/bugs/ (not yet implemented)"
fi

# t2: scope-guard.sh source contains a path-based check for .claude/backlogs/
if grep -q 'backlogs' "$SCOPE_GUARD" 2>/dev/null; then
    ok 2 "scope-guard.sh contains path-based check for .claude/backlogs/"
else
    fail_t 2 "scope-guard.sh does NOT contain a path-based check for .claude/backlogs/ (not yet implemented)"
fi

# t3: run.sh does NOT contain "test-backlog-e2e-tdd.sh"
if ! grep -q 'test-backlog-e2e-tdd.sh' "$RUN_SH" 2>/dev/null; then
    ok 3 "run.sh does not contain test-backlog-e2e-tdd.sh (suite removed)"
else
    fail_t 3 "run.sh still contains test-backlog-e2e-tdd.sh (not yet removed)"
fi

# t4: test-claude-md.sh does NOT assert that test-backlog-e2e-tdd.sh IS in run.sh
# The old t9 positive assertion grepped for "test-backlog-e2e-tdd.sh" in run.sh and expected it present.
# After migration, that positive assertion must be gone.
# We look for any line in test-claude-md.sh that checks for test-backlog-e2e-tdd in run.sh
# as a positive assertion (i.e., ok/pass on finding it).
if ! grep -q 'test-backlog-e2e-tdd' "$TEST_CLAUDE_MD" 2>/dev/null; then
    ok 4 "test-claude-md.sh does not reference test-backlog-e2e-tdd.sh at all (old t9 removed)"
else
    fail_t 4 "test-claude-md.sh still references test-backlog-e2e-tdd.sh (old t9 positive assertion not yet removed)"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
