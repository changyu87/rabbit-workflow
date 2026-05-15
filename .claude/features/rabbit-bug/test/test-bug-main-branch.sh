#!/usr/bin/env bash
# test-bug-main-branch.sh
# Tests for main-branch guard in file-bug.sh and user-decision gate in SKILL.md.
#
# t_mb1: file-bug.sh exits non-zero when current branch is not main (no tty, non-interactive)
# t_mb2: file-bug.sh succeeds when current branch is main
# t_mb3: file-bug.sh prints a warning to stderr when not on main branch
# t_mb4: SKILL.md Working Protocol contains user-decision gate language (brief + ask before dispatch)
#
# Exit: 1 if any assertion fails.

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$FEATURE_DIR/scripts"
SKILL_MD="$FEATURE_DIR/skills/rabbit-bug/SKILL.md"

pass=0
fail=0

assert_pass() {
    local label="$1"
    echo "PASS: $label"
    pass=$((pass + 1))
}

assert_fail() {
    local label="$1"
    local reason="$2"
    echo "FAIL: $label — $reason"
    fail=$((fail + 1))
}

# ---------------------------------------------------------------------------
# Setup: create a temp git repo with a feature for filing bugs
# ---------------------------------------------------------------------------
TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

GIT_REPO="$TMPDIR_ROOT/test-repo"
mkdir -p "$GIT_REPO"
git -C "$GIT_REPO" init -q
git -C "$GIT_REPO" config user.email "test@example.com"
git -C "$GIT_REPO" config user.name "Test User"

# Make an initial commit on main
touch "$GIT_REPO/README"
git -C "$GIT_REPO" add README
git -C "$GIT_REPO" commit -q -m "init"

# Ensure default branch is named 'main'
CURRENT_BRANCH="$(git -C "$GIT_REPO" branch --show-current 2>/dev/null)"
if [ "$CURRENT_BRANCH" != "main" ]; then
    git -C "$GIT_REPO" branch -m "$CURRENT_BRANCH" main 2>/dev/null || true
fi

# Install find-feature.sh
REPO_ROOT_REAL="${RABBIT_ROOT:-$(git -C "$SCRIPTS_DIR" rev-parse --show-toplevel 2>/dev/null)}"
FIND_FEATURE_SRC="$REPO_ROOT_REAL/.claude/features/contract/scripts/find-feature.sh"
mkdir -p "$GIT_REPO/.claude/features/contract/scripts"
cp "$FIND_FEATURE_SRC" "$GIT_REPO/.claude/features/contract/scripts/find-feature.sh"
cp "$(dirname "$FIND_FEATURE_SRC")/find-feature.py" "$GIT_REPO/.claude/features/contract/scripts/find-feature.py"
chmod +x "$GIT_REPO/.claude/features/contract/scripts/find-feature.sh"

# Create feature.json for test-feature
mkdir -p "$GIT_REPO/.claude/features/test-feature"
cat > "$GIT_REPO/.claude/features/test-feature/feature.json" <<'FEATEOF'
{
  "name": "test-feature",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "Test feature for main-branch tests."
}
FEATEOF

# Create a non-main branch in the repo
git -C "$GIT_REPO" checkout -q -b "feature/some-work" 2>/dev/null

# ---------------------------------------------------------------------------
# t_mb1: file-bug.sh exits non-zero when current branch is not main
#         (no /dev/tty input available in this test context)
# ---------------------------------------------------------------------------
T_MB1_LABEL="t_mb1: file-bug.sh exits non-zero when not on main branch"

(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature test-feature \
    < /dev/null > /tmp/mb1_stdout.txt 2> /tmp/mb1_stderr.txt)
T_MB1_EXIT=$?

if [ $T_MB1_EXIT -ne 0 ]; then
    assert_pass "$T_MB1_LABEL"
else
    assert_fail "$T_MB1_LABEL" "file-bug.sh exited 0 on non-main branch (expected non-zero)"
fi

# ---------------------------------------------------------------------------
# t_mb2: file-bug.sh succeeds when current branch is main
# ---------------------------------------------------------------------------
T_MB2_LABEL="t_mb2: file-bug.sh succeeds when current branch is main"

git -C "$GIT_REPO" checkout -q main 2>/dev/null

(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature test-feature \
    > /dev/null 2>&1)
T_MB2_EXIT=$?

if [ $T_MB2_EXIT -eq 0 ]; then
    assert_pass "$T_MB2_LABEL"
else
    assert_fail "$T_MB2_LABEL" "file-bug.sh exited $T_MB2_EXIT on main branch (expected 0)"
fi

# Switch back to non-main for remaining tests
git -C "$GIT_REPO" checkout -q "feature/some-work" 2>/dev/null

# ---------------------------------------------------------------------------
# t_mb3: file-bug.sh prints a warning to stderr when not on main branch
# ---------------------------------------------------------------------------
T_MB3_LABEL="t_mb3: file-bug.sh prints warning to stderr when not on main branch"

(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature test-feature \
    < /dev/null > /dev/null 2> /tmp/mb3_stderr.txt) || true

STDERR_CONTENT="$(cat /tmp/mb3_stderr.txt 2>/dev/null)"

if echo "$STDERR_CONTENT" | grep -qi "warn\|not.*main\|main.*branch\|branch.*main"; then
    assert_pass "$T_MB3_LABEL"
else
    assert_fail "$T_MB3_LABEL" "no branch warning found in stderr: '$STDERR_CONTENT'"
fi

# ---------------------------------------------------------------------------
# t_mb4: SKILL.md Working Protocol contains user-decision gate language
# ---------------------------------------------------------------------------
T_MB4_LABEL="t_mb4: SKILL.md Working Protocol has user-decision gate (brief + ask before dispatch)"

if [ ! -f "$SKILL_MD" ]; then
    assert_fail "$T_MB4_LABEL" "SKILL.md not found at $SKILL_MD"
else
    # Check for language indicating: (1) brief/summary to user, (2) ask/confirm before dispatching
    HAS_BRIEF=0
    HAS_ASK=0
    if grep -qi "brief\|summary\|recommendation\|eval.*summary\|eval.*finding\|summarize" "$SKILL_MD"; then
        HAS_BRIEF=1
    fi
    if grep -qi "ask\|confirm\|whether.*refuse\|whether.*work\|before.*dispatch\|before.*rabbit-feature-touch\|user.*decide\|decision" "$SKILL_MD"; then
        HAS_ASK=1
    fi
    if [ "$HAS_BRIEF" -eq 1 ] && [ "$HAS_ASK" -eq 1 ]; then
        assert_pass "$T_MB4_LABEL"
    else
        assert_fail "$T_MB4_LABEL" "missing gate language — HAS_BRIEF=$HAS_BRIEF HAS_ASK=$HAS_ASK (both must be 1)"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Results: $pass passed, $fail failed"

if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
