#!/usr/bin/env bash
# test-POLICY-BACKLOG-1-session-init-branch.sh
# Tests for session-init.sh R1 branch-per-session enforcement.
#
# Spec invariants tested:
#   t1: When on 'main', session-init.sh creates and checks out a session/YYYYMMDD-HHMMSS branch
#   t2: When on a non-main branch, session-init.sh does NOT create or switch branches
#   t3: Created branch name follows the session/ prefix and YYYYMMDD-HHMMSS timestamp format
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
# t1: When on 'main', hook creates and checks out a session/... branch
# ---------------------------------------------------------------------------
echo "=== t1: on main → creates session/ branch ==="

REPO1="$(make_repo)"
trap 'rm -rf "$REPO1"' EXIT

RABBIT_ROOT="$REPO1" bash "$HOOK" > /dev/null 2>&1 || true

BRANCH_T1="$(git -C "$REPO1" branch --show-current 2>/dev/null)"

if [ "$BRANCH_T1" != "main" ] && [[ "$BRANCH_T1" == session/* ]]; then
    ok "hook switched away from main to '$BRANCH_T1'"
else
    fail_t "hook did NOT switch from main; current branch: '$BRANCH_T1' (expected session/...)"
fi

# ---------------------------------------------------------------------------
# t2: When on a non-main branch, hook does nothing to the branch
# ---------------------------------------------------------------------------
echo ""
echo "=== t2: on feature branch → no branch change ==="

REPO2="$(make_repo)"
trap 'rm -rf "$REPO1" "$REPO2"' EXIT

git -C "$REPO2" checkout -q -b "feature/keep-this" 2>/dev/null

RABBIT_ROOT="$REPO2" bash "$HOOK" > /dev/null 2>&1 || true

BRANCH_T2="$(git -C "$REPO2" branch --show-current 2>/dev/null)"

if [ "$BRANCH_T2" = "feature/keep-this" ]; then
    ok "hook left branch unchanged at '$BRANCH_T2'"
else
    fail_t "hook changed branch from 'feature/keep-this' to '$BRANCH_T2' when already on non-main branch"
fi

# ---------------------------------------------------------------------------
# t3: Branch name follows session/YYYYMMDD-HHMMSS format
# ---------------------------------------------------------------------------
echo ""
echo "=== t3: branch name follows session/YYYYMMDD-HHMMSS format ==="

REPO3="$(make_repo)"
trap 'rm -rf "$REPO1" "$REPO2" "$REPO3"' EXIT

RABBIT_ROOT="$REPO3" bash "$HOOK" > /dev/null 2>&1 || true

BRANCH_T3="$(git -C "$REPO3" branch --show-current 2>/dev/null)"

if [[ "$BRANCH_T3" =~ ^session/[0-9]{8}-[0-9]{6}$ ]]; then
    ok "branch '$BRANCH_T3' matches session/YYYYMMDD-HHMMSS format"
else
    fail_t "branch '$BRANCH_T3' does NOT match session/YYYYMMDD-HHMMSS format (expected e.g. session/20260512-143000)"
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
