#!/usr/bin/env bash
# rabbit-cage obsolete artifact removal tests
# Tests that all obsolete features and artifacts are gone after migration.
# All tests must FAIL before implementation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
FEATURES="$REPO_ROOT/.claude/features"

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

echo "test-obsolete-removed.sh"

# t1: .claude/features/root-management/ does NOT exist
if [ ! -e "$FEATURES/root-management" ]; then
    ok 1 "root-management feature removed"
else
    fail_t 1 "root-management feature still exists at $FEATURES/root-management"
fi

# t2: .claude/features/policy-enforcement/ does NOT exist
if [ ! -e "$FEATURES/policy-enforcement" ]; then
    ok 2 "policy-enforcement feature removed"
else
    fail_t 2 "policy-enforcement feature still exists at $FEATURES/policy-enforcement"
fi

# t3: .claude/features/subagent-policy-injection/ does NOT exist
if [ ! -e "$FEATURES/subagent-policy-injection" ]; then
    ok 3 "subagent-policy-injection feature removed"
else
    fail_t 3 "subagent-policy-injection feature still exists at $FEATURES/subagent-policy-injection"
fi

# t4: .claude/features/breeder/ does NOT exist
if [ ! -e "$FEATURES/breeder" ]; then
    ok 4 "breeder feature removed"
else
    fail_t 4 "breeder feature still exists at $FEATURES/breeder"
fi

# t5: .claude/features/vet/ does NOT exist
if [ ! -e "$FEATURES/vet" ]; then
    ok 5 "vet feature removed"
else
    fail_t 5 "vet feature still exists at $FEATURES/vet"
fi

# t6: .claude/agents/rabbit-breeder.md does NOT exist
if [ ! -e "$REPO_ROOT/.claude/agents/rabbit-breeder.md" ]; then
    ok 6 "rabbit-breeder.md agent removed"
else
    fail_t 6 "rabbit-breeder.md still exists at .claude/agents/rabbit-breeder.md"
fi

# t7: .claude/agents/rabbit-vet.md does NOT exist
if [ ! -e "$REPO_ROOT/.claude/agents/rabbit-vet.md" ]; then
    ok 7 "rabbit-vet.md agent removed"
else
    fail_t 7 "rabbit-vet.md still exists at .claude/agents/rabbit-vet.md"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
