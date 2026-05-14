#!/usr/bin/env bash
# test-POLICY-BACKLOG-1-session-init-branch.sh
# Tests that session-init.sh does NOT create session/ branches (R1 removed).
#
# Spec invariants tested:
#   t1: When on 'main', session-init.sh does NOT create or switch branches
#   t2: When on a feature branch, session-init.sh does NOT create or switch branches
#   t3: session-init.sh emits valid JSON (additionalContext present) when @-imports resolve
#
# R3-compliant: no interactive constructs, exits 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
HOOK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/session-init.sh"

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

echo "test-POLICY-BACKLOG-1-session-init-branch.sh"
echo ""

# Helper: create a minimal temp git repo with 'main' as default branch.
make_repo() {
    local d
    d="$(mktemp -d)"
    git init -q "$d"
    git -C "$d" config user.email "test@test.com"
    git -C "$d" config user.name "Test"
    git -C "$d" checkout -q -b main 2>/dev/null || true
    touch "$d/placeholder"
    git -C "$d" add placeholder
    git -C "$d" commit -q -m "init"
    mkdir -p "$d/.claude"
    printf '# Test CLAUDE.md\n' > "$d/CLAUDE.md"
    echo "$d"
}

# ---------------------------------------------------------------------------
# t1: When on 'main', hook does NOT create or switch branches
# ---------------------------------------------------------------------------
echo "=== t1: on main → branch unchanged ==="

REPO1="$(make_repo)"
trap 'rm -rf "$REPO1"' EXIT

RABBIT_ROOT="$REPO1" bash "$HOOK" > /dev/null 2>&1 || true

BRANCH_T1="$(git -C "$REPO1" branch --show-current 2>/dev/null)"

if [ "$BRANCH_T1" = "main" ]; then
    ok "hook left branch unchanged at 'main'"
else
    fail_t "hook changed branch from 'main' to '$BRANCH_T1' (R1 branch creation should be removed)"
fi

# ---------------------------------------------------------------------------
# t2: When on a feature branch, hook does NOT create or switch branches
# ---------------------------------------------------------------------------
echo ""
echo "=== t2: on feature branch → no branch change ==="

REPO2="$(make_repo)"
trap 'rm -rf "$REPO1" "$REPO2"' EXIT

git -C "$REPO2" checkout -q -b "feature/keep-this" 2>/dev/null

RABBIT_ROOT="$REPO2" bash "$HOOK" > /dev/null 2>&1 || true

BRANCH_T2="$(git -C "$REPO2" branch --show-current 2>/dev/null)"

if [ "$BRANCH_T2" = "feature/keep-this" ]; then
    ok "hook left branch unchanged at 'feature/keep-this'"
else
    fail_t "hook changed branch from 'feature/keep-this' to '$BRANCH_T2'"
fi

# ---------------------------------------------------------------------------
# t3: session-init.sh emits valid JSON with additionalContext when @-imports resolve
# ---------------------------------------------------------------------------
echo ""
echo "=== t3: @-import injection emits valid JSON ==="

OUTPUT="$(RABBIT_ROOT="$REPO_ROOT" bash "$HOOK" 2>/dev/null || true)"

if echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'additionalContext' in d" 2>/dev/null; then
    ok "@-import injection emits valid JSON with additionalContext"
else
    fail_t "@-import injection did not emit valid JSON with additionalContext"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [ "$FAILURES" -eq 0 ]; then
    echo "test-POLICY-BACKLOG-1-session-init-branch.sh: ALL $TOTAL PASSED"
    exit 0
else
    echo "test-POLICY-BACKLOG-1-session-init-branch.sh: $FAILURES/$TOTAL FAILED"
    exit 1
fi
