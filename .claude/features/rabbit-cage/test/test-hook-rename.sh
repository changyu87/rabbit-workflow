#!/usr/bin/env bash
# test-hook-rename.sh
# Tests that hook files in rabbit-cage/hooks/ have been renamed to drop the rbt- prefix.
# Also asserts no tracked file in the repo (outside archive/) still references the old names.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.claude/features/rabbit-cage/hooks"
# Relative path from repo root for git grep exclusion (e.g. .claude/features/rabbit-cage/test/test-hook-rename.sh)
SCRIPT_REL="$(realpath --relative-to="$REPO_ROOT" "${BASH_SOURCE[0]}")"

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

echo "test-hook-rename.sh"

OLD1="rbt-refresh.sh"
OLD2="rbt-session-init.sh"
OLD3="rbt-sync-check.sh"

# t1: rbt-refresh.sh does NOT exist in hooks/
if [ ! -f "$HOOKS_DIR/$OLD1" ]; then
    ok 1 "$OLD1 does not exist in hooks/ (old name gone)"
else
    fail_t 1 "$OLD1 still exists in hooks/ — rename not done"
fi

# t2: rbt-session-init.sh does NOT exist in hooks/
if [ ! -f "$HOOKS_DIR/$OLD2" ]; then
    ok 2 "$OLD2 does not exist in hooks/ (old name gone)"
else
    fail_t 2 "$OLD2 still exists in hooks/ — rename not done"
fi

# t3: rbt-sync-check.sh does NOT exist in hooks/
if [ ! -f "$HOOKS_DIR/$OLD3" ]; then
    ok 3 "$OLD3 does not exist in hooks/ (old name gone)"
else
    fail_t 3 "$OLD3 still exists in hooks/ — rename not done"
fi

# t4: refresh.sh exists in hooks/
if [ -f "$HOOKS_DIR/refresh.sh" ]; then
    ok 4 "refresh.sh exists in hooks/ (new name present)"
else
    fail_t 4 "refresh.sh does not exist in hooks/ — rename not done"
fi

# t5: session-init.sh exists in hooks/
if [ -f "$HOOKS_DIR/session-init.sh" ]; then
    ok 5 "session-init.sh exists in hooks/ (new name present)"
else
    fail_t 5 "session-init.sh does not exist in hooks/ — rename not done"
fi

# t6: sync-check.sh exists in hooks/
if [ -f "$HOOKS_DIR/sync-check.sh" ]; then
    ok 6 "sync-check.sh exists in hooks/ (new name present)"
else
    fail_t 6 "sync-check.sh does not exist in hooks/ — rename not done"
fi

# t7: no tracked file outside archive/ references rbt-refresh.sh
# We check git-tracked files only; grep -l returns filenames; exclude this test file itself.
OLD_REFS="$(git -C "$REPO_ROOT" grep -l 'rbt-refresh\.sh' -- ':!archive/' ':!'"$SCRIPT_REL" 2>/dev/null || true)"
if [ -z "$OLD_REFS" ]; then
    ok 7 "no tracked file (outside archive/) references $OLD1"
else
    fail_t 7 "tracked files still reference $OLD1: $(echo "$OLD_REFS" | tr '\n' ' ')"
fi

# t8: no tracked file outside archive/ references rbt-session-init.sh
OLD_REFS="$(git -C "$REPO_ROOT" grep -l 'rbt-session-init\.sh' -- ':!archive/' ':!'"$SCRIPT_REL" 2>/dev/null || true)"
if [ -z "$OLD_REFS" ]; then
    ok 8 "no tracked file (outside archive/) references $OLD2"
else
    fail_t 8 "tracked files still reference $OLD2: $(echo "$OLD_REFS" | tr '\n' ' ')"
fi

# t9: no tracked file outside archive/ references rbt-sync-check.sh
OLD_REFS="$(git -C "$REPO_ROOT" grep -l 'rbt-sync-check\.sh' -- ':!archive/' ':!'"$SCRIPT_REL" 2>/dev/null || true)"
if [ -z "$OLD_REFS" ]; then
    ok 9 "no tracked file (outside archive/) references $OLD3"
else
    fail_t 9 "tracked files still reference $OLD3: $(echo "$OLD_REFS" | tr '\n' ' ')"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
