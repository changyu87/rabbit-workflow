#!/usr/bin/env bash
# test-no-embedded-python3.sh
# Updated for the .sh→.py whole-script migration (RABBIT-CAGE-BACKLOG-2):
# the original "no embedded python3 in .sh" invariant is now subsumed by the
# stricter "no .sh files in hooks/ or scripts/" invariant (Spec Inv 39).
#
# This test asserts:
#   t1-t2: hooks/ and scripts/ contain NO .sh files.
#   t3+:   the standalone Python helper files declared in Inv 40 still exist.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
HOOKS_DIR="$REPO_ROOT/.claude/features/rabbit-cage/hooks"
SCRIPTS_DIR="$REPO_ROOT/.claude/features/rabbit-cage/scripts"

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

echo "test-no-embedded-python3.sh"
echo ""

echo "=== hooks/ has no .sh files ==="
sh_in_hooks="$(find "$HOOKS_DIR" -maxdepth 1 -type f -name '*.sh' 2>/dev/null)"
if [ -z "$sh_in_hooks" ]; then
    ok "hooks/ has no .sh files"
else
    fail_t "hooks/ still contains .sh files: $sh_in_hooks"
fi

echo "=== scripts/ has no .sh files ==="
sh_in_scripts="$(find "$SCRIPTS_DIR" -maxdepth 1 -type f -name '*.sh' 2>/dev/null)"
if [ -z "$sh_in_scripts" ]; then
    ok "scripts/ has no .sh files"
else
    fail_t "scripts/ still contains .sh files: $sh_in_scripts"
fi

# Helper: check a .py helper file exists
check_py_helper_exists() {
    local pyfile="$1"
    echo "=== $pyfile exists ==="
    if [ -f "$SCRIPTS_DIR/$pyfile" ]; then
        ok "$pyfile exists"
    else
        fail_t "$pyfile does not exist (expected Python helper per Inv 40)"
    fi
}

check_py_helper_exists "workspace-tree.py"
check_py_helper_exists "rabbit-project-set-path.py"
check_py_helper_exists "rabbit-project-map.py"
check_py_helper_exists "rabbit-project-consolidate.py"
check_py_helper_exists "build-targets.py"
check_py_helper_exists "generate-claude-md-header.py"

echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
