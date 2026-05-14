#!/usr/bin/env bash
# test-no-embedded-python3.sh
# Asserts that rabbit-cage bash scripts contain NO embedded python3 heredocs
# (python3 - ... <<'PYEOF') or inline python3 -c calls.
#
# Affected scripts: workspace-tree.sh, rabbit-project.sh, build.sh, generate-claude-md.sh
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
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

# Helper: check a script has no embedded python3 heredoc
# Detects: python3 - [args] << or python3 - << patterns
check_no_heredoc() {
    local script="$1"
    local label="$2"
    echo "=== $label: no python3 heredoc ==="
    if [ ! -f "$SCRIPTS_DIR/$script" ]; then
        fail_t "$script not found"
        return
    fi
    # grep for lines that have "python3" followed by "-" and look for heredoc marker
    if grep -E 'python3[[:space:]]+-[[:space:]]*' "$SCRIPTS_DIR/$script" | grep -qE '<<'; then
        MATCHES="$(grep -n 'python3' "$SCRIPTS_DIR/$script" | head -5)"
        fail_t "$script contains embedded python3 heredoc:
$MATCHES"
    else
        ok "$script has no embedded python3 heredoc"
    fi
}

# Helper: check a script has no inline python3 -c call
check_no_inline_python() {
    local script="$1"
    local label="$2"
    echo "=== $label: no python3 -c ==="
    if [ ! -f "$SCRIPTS_DIR/$script" ]; then
        fail_t "$script not found"
        return
    fi
    if grep -qE 'python3[[:space:]]+-c[[:space:]]' "$SCRIPTS_DIR/$script" 2>/dev/null; then
        MATCHES="$(grep -n 'python3 -c' "$SCRIPTS_DIR/$script" | head -5)"
        fail_t "$script contains inline python3 -c call:
$MATCHES"
    else
        ok "$script has no inline python3 -c call"
    fi
}

# Helper: check a .py helper file exists
check_py_helper_exists() {
    local pyfile="$1"
    local label="$2"
    echo "=== $label: $pyfile exists ==="
    if [ -f "$SCRIPTS_DIR/$pyfile" ]; then
        ok "$pyfile exists"
    else
        fail_t "$pyfile does not exist (expected Python helper)"
    fi
}

# ---------------------------------------------------------------------------
# workspace-tree.sh: no heredoc, no python3 -c
# ---------------------------------------------------------------------------
check_no_heredoc "workspace-tree.sh" "workspace-tree.sh"
check_no_inline_python "workspace-tree.sh" "workspace-tree.sh"

# ---------------------------------------------------------------------------
# rabbit-project.sh: no heredoc, no python3 -c
# ---------------------------------------------------------------------------
check_no_heredoc "rabbit-project.sh" "rabbit-project.sh"
check_no_inline_python "rabbit-project.sh" "rabbit-project.sh"

# ---------------------------------------------------------------------------
# build.sh: no heredoc, no python3 -c
# ---------------------------------------------------------------------------
check_no_heredoc "build.sh" "build.sh"
check_no_inline_python "build.sh" "build.sh"

# ---------------------------------------------------------------------------
# generate-claude-md.sh: no heredoc, no python3 -c
# ---------------------------------------------------------------------------
check_no_heredoc "generate-claude-md.sh" "generate-claude-md.sh"
check_no_inline_python "generate-claude-md.sh" "generate-claude-md.sh"

# ---------------------------------------------------------------------------
# Python helper files must exist
# ---------------------------------------------------------------------------
check_py_helper_exists "workspace-tree.py" "workspace-tree.py helper"
check_py_helper_exists "rabbit-project-set-path.py" "rabbit-project-set-path.py helper"
check_py_helper_exists "rabbit-project-map.py" "rabbit-project-map.py helper"
check_py_helper_exists "rabbit-project-consolidate.py" "rabbit-project-consolidate.py helper"
check_py_helper_exists "build-targets.py" "build-targets.py helper"
check_py_helper_exists "generate-claude-md-header.py" "generate-claude-md-header.py helper"

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
