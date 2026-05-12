#!/usr/bin/env bash
# test-RABBIT-CAGE-19-confirm-token-override.sh
# Tests that spec and contract reflect the confirm-token override approval flow.
#
# Asserts:
#   (a) spec no longer contains human-only authoring restriction on .rabbit-scope-override
#   (b) spec documents the confirm-token approval flow
#   (c) contract "never" list no longer forbids Claude writing .rabbit-scope-override
#   (d) contract runtime_markers writer field for .rabbit-scope-override includes Claude
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SPEC="$REPO_ROOT/.claude/features/rabbit-cage/docs/spec/spec.md"
CONTRACT="$REPO_ROOT/.claude/features/rabbit-cage/docs/spec/contract.md"

FAILURES=0
TOTAL=0

ok() {
    TOTAL=$(( TOTAL + 1 ))
    echo "  PASS t$TOTAL: $1"
}

fail_t() {
    TOTAL=$(( TOTAL + 1 ))
    FAILURES=$(( FAILURES + 1 ))
    echo "  FAIL t$TOTAL: $1"
}

echo "test-RABBIT-CAGE-19-confirm-token-override.sh"
echo ""
echo "=== SPEC: human-only authoring restriction removed ==="

# t1: spec must NOT contain the human-only authoring restriction text
if ! grep -qF 'only a human creates this file' "$SPEC" 2>/dev/null; then
    ok "spec does not contain 'only a human creates this file' restriction"
else
    fail_t "spec still contains 'only a human creates this file' -- human-only restriction not removed"
fi

# t2: spec must NOT contain the old out-of-scope bullet about human-only authoring
if ! grep -q 'Authoring.*rabbit-scope-override.*only a human' "$SPEC" 2>/dev/null; then
    ok "spec does not contain old human-only authoring out-of-scope bullet"
else
    fail_t "spec still contains old human-only authoring out-of-scope bullet"
fi

echo ""
echo "=== SPEC: confirm-token flow documented ==="

# t3: spec must contain "confirm-token" or "confirm token" (new flow name)
if grep -qiE 'confirm.?token' "$SPEC" 2>/dev/null; then
    ok "spec documents confirm-token approval flow"
else
    fail_t "spec does NOT document confirm-token approval flow"
fi

# t4: spec must indicate main session may write .rabbit-scope-override after user approval
if grep -qE '(main session|Claude).*write.*rabbit-scope-override|rabbit-scope-override.*write.*(main session|Claude)' "$SPEC" 2>/dev/null; then
    ok "spec states main session/Claude may write .rabbit-scope-override after approval"
else
    fail_t "spec does not state main session/Claude may write .rabbit-scope-override after approval"
fi

# t5: spec must reference in-conversation approval
if grep -qE 'in-conversation' "$SPEC" 2>/dev/null; then
    ok "spec references in-conversation approval"
else
    fail_t "spec does NOT reference in-conversation approval"
fi

echo ""
echo "=== CONTRACT: never list updated ==="

# t6: contract "never" list must NOT contain the human-only authoring entry
if ! grep -qF 'creates .rabbit-scope-override (human-only authoring)' "$CONTRACT" 2>/dev/null; then
    ok "contract never-list does not forbid Claude writing .rabbit-scope-override"
else
    fail_t "contract never-list still contains 'creates .rabbit-scope-override (human-only authoring)'"
fi

echo ""
echo "=== CONTRACT: runtime_markers writer updated ==="

# t7: contract runtime_markers writer for .rabbit-scope-override must include Claude
if grep -qE '"writer".*Claude' "$CONTRACT" 2>/dev/null; then
    ok "contract runtime_markers writer field includes Claude for .rabbit-scope-override"
else
    fail_t "contract runtime_markers writer field does NOT include Claude for .rabbit-scope-override"
fi

# t8: contract runtime_markers must reference in-conversation approval
if grep -qE 'in-conversation' "$CONTRACT" 2>/dev/null; then
    ok "contract runtime_markers references in-conversation approval condition"
else
    fail_t "contract runtime_markers does NOT reference in-conversation approval condition"
fi

echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
