#!/usr/bin/env bash
# test-bug-changes.sh
# Failing tests for pending changes to the rabbit-bug feature.
#
# t_bug1: --reason accepted (replaces --note) — transition succeeds with --reason
# t_bug2: --note alone (without --reason) exits non-zero
# t_bug3: --reason is required on set — omitting it exits non-zero
# t_bug4: --fix-commits required on closed — missing --fix-commits (and no --skip-vet-reason) exits non-zero
# t_bug5: --fix-commits accepted on closed — transition succeeds when provided
# t_bug6: --fix-commits rejected on refused — providing it exits non-zero
# t_bug7: git commit created after successful set transition
# t_bug8: git commit created after file-bug.sh creates a bug
#
# Exit: 1 if any assertion fails.

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$FEATURE_DIR/scripts"

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
# Setup: create a temp git repo and a fresh bug for tests that need one
# ---------------------------------------------------------------------------
TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

GIT_REPO="$TMPDIR_ROOT/test-repo"
mkdir -p "$GIT_REPO"
git -C "$GIT_REPO" init -q
git -C "$GIT_REPO" config user.email "test@example.com"
git -C "$GIT_REPO" config user.name "Test User"

# Make an initial commit so git log works
touch "$GIT_REPO/README"
git -C "$GIT_REPO" add README
git -C "$GIT_REPO" commit -q -m "init"
# Ensure branch is 'main' so file-bug.sh main-branch guard passes
_INIT_BRANCH="$(git -C "$GIT_REPO" branch --show-current 2>/dev/null)"
[ "$_INIT_BRANCH" != "main" ] && git -C "$GIT_REPO" branch -m "$_INIT_BRANCH" main 2>/dev/null || true

# Install find-feature.sh so file-bug.sh can validate the feature.
REPO_ROOT_REAL="${RABBIT_ROOT:-$(git -C "$SCRIPTS_DIR" rev-parse --show-toplevel 2>/dev/null)}"
FIND_FEATURE_SRC="$REPO_ROOT_REAL/.claude/features/contract/scripts/find-feature.sh"
mkdir -p "$GIT_REPO/.claude/features/contract/scripts"
cp "$FIND_FEATURE_SRC" "$GIT_REPO/.claude/features/contract/scripts/find-feature.sh"
cp "$(dirname "$FIND_FEATURE_SRC")/find-feature.py" "$GIT_REPO/.claude/features/contract/scripts/find-feature.py"
chmod +x "$GIT_REPO/.claude/features/contract/scripts/find-feature.sh"

# Create feature.json for test-feature so find-feature.sh can discover it.
mkdir -p "$GIT_REPO/.claude/features/test-feature"
cat > "$GIT_REPO/.claude/features/test-feature/feature.json" <<'FEATEOF'
{
  "name": "test-feature",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "Test feature for bug changes tests."
}
FEATEOF

# ---------------------------------------------------------------------------
# Helper: create a minimal bug.json in a temp dir (not inside a git repo)
# ---------------------------------------------------------------------------
make_bug_dir() {
    local bug_dir="$1"
    mkdir -p "$bug_dir"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    jq -n \
        --arg ts "$ts" \
        '{name:"TEST-BUG-1",title:"Test Bug",status:"open",severity:"low",
          description:"test desc",related_feature:"test-feature",
          filed:$ts,filed_by:"tester",closed:null,closed_by:null,
          history:[{ts:$ts,actor:"tester",action:"opened",note:"initial filing"}]}' \
        > "$bug_dir/bug.json"
}

# ---------------------------------------------------------------------------
# t_bug1: --reason accepted (replaces --note) — transition succeeds with --reason
# ---------------------------------------------------------------------------
T_BUG1_LABEL="t_bug1: --reason accepted (replaces --note) — transition succeeds with --reason"

BUG1_DIR="$TMPDIR_ROOT/bug1"
make_bug_dir "$BUG1_DIR"

bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG1_DIR" refused \
    --reason "test reason" \
    --skip-vet-reason "bypass" \
    > /dev/null 2>&1
T_BUG1_EXIT=$?

if [ $T_BUG1_EXIT -eq 0 ]; then
    assert_pass "$T_BUG1_LABEL"
else
    assert_fail "$T_BUG1_LABEL" "bug-status.sh set with --reason exited $T_BUG1_EXIT (expected 0)"
fi

# ---------------------------------------------------------------------------
# t_bug2: --note alone (without --reason) exits non-zero
# ---------------------------------------------------------------------------
T_BUG2_LABEL="t_bug2: --note alone (without --reason) exits non-zero"

BUG2_DIR="$TMPDIR_ROOT/bug2"
make_bug_dir "$BUG2_DIR"

bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG2_DIR" refused \
    --note "old note" \
    --skip-vet-reason "bypass" \
    > /dev/null 2>&1
T_BUG2_EXIT=$?

if [ $T_BUG2_EXIT -ne 0 ]; then
    assert_pass "$T_BUG2_LABEL"
else
    assert_fail "$T_BUG2_LABEL" "bug-status.sh set with --note exited 0 (expected non-zero; --note should be rejected)"
fi

# ---------------------------------------------------------------------------
# t_bug3: --reason is required on set — omitting it exits non-zero
# ---------------------------------------------------------------------------
T_BUG3_LABEL="t_bug3: --reason required on set — omitting it exits non-zero"

BUG3_DIR="$TMPDIR_ROOT/bug3"
make_bug_dir "$BUG3_DIR"

bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG3_DIR" refused \
    --skip-vet-reason "bypass" \
    > /dev/null 2>&1
T_BUG3_EXIT=$?

if [ $T_BUG3_EXIT -ne 0 ]; then
    assert_pass "$T_BUG3_LABEL"
else
    assert_fail "$T_BUG3_LABEL" "bug-status.sh set without --reason exited 0 (expected non-zero)"
fi

# ---------------------------------------------------------------------------
# t_bug4: --fix-commits required on closed — missing it exits non-zero
#
# Use --note (accepted by current code) so the only variable is whether
# --fix-commits is present. Current code accepts the transition (exit 0),
# so the assertion ne 0 FAILS now. After implementation --fix-commits is
# required on closed, so it exits non-zero and the assertion PASSES.
# ---------------------------------------------------------------------------
T_BUG4_LABEL="t_bug4: --fix-commits required on closed — missing it exits non-zero"

BUG4_DIR="$TMPDIR_ROOT/bug4"
make_bug_dir "$BUG4_DIR"

bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG4_DIR" closed \
    --note "closing it" \
    --skip-vet-reason "bypass" \
    > /dev/null 2>&1
T_BUG4_EXIT=$?

if [ $T_BUG4_EXIT -ne 0 ]; then
    assert_pass "$T_BUG4_LABEL"
else
    assert_fail "$T_BUG4_LABEL" "bug-status.sh set closed without --fix-commits exited 0 (expected non-zero)"
fi

# ---------------------------------------------------------------------------
# t_bug5: --fix-commits accepted on closed — transition succeeds when provided
# ---------------------------------------------------------------------------
T_BUG5_LABEL="t_bug5: --fix-commits accepted on closed — transition succeeds when provided"

BUG5_DIR="$TMPDIR_ROOT/bug5"
make_bug_dir "$BUG5_DIR"

bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG5_DIR" closed \
    --reason "fixed it" \
    --fix-commits "abc123" \
    --skip-vet-reason "bypass" \
    > /dev/null 2>&1
T_BUG5_EXIT=$?

if [ $T_BUG5_EXIT -eq 0 ]; then
    assert_pass "$T_BUG5_LABEL"
else
    assert_fail "$T_BUG5_LABEL" "bug-status.sh set closed with --fix-commits exited $T_BUG5_EXIT (expected 0)"
fi

# ---------------------------------------------------------------------------
# t_bug6: --fix-commits rejected on refused — providing it exits non-zero
#
# Use --note (accepted by current code) so the only variable is whether
# --fix-commits is rejected on refused. Current code accepts --fix-commits
# on refused (exit 0), so the assertion ne 0 FAILS now. After implementation
# --fix-commits on refused is rejected (exit non-zero) and the assertion PASSES.
# ---------------------------------------------------------------------------
T_BUG6_LABEL="t_bug6: --fix-commits rejected on refused — providing it exits non-zero"

BUG6_DIR="$TMPDIR_ROOT/bug6"
make_bug_dir "$BUG6_DIR"

bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG6_DIR" refused \
    --note "wontfix" \
    --fix-commits "abc123" \
    --skip-vet-reason "bypass" \
    > /dev/null 2>&1
T_BUG6_EXIT=$?

if [ $T_BUG6_EXIT -ne 0 ]; then
    assert_pass "$T_BUG6_LABEL"
else
    assert_fail "$T_BUG6_LABEL" "bug-status.sh set refused with --fix-commits exited 0 (expected non-zero)"
fi

# ---------------------------------------------------------------------------
# t_bug7: git commit created after successful set transition
# ---------------------------------------------------------------------------
T_BUG7_LABEL="t_bug7: git commit created after successful set transition"

BUG7_ROOT="$GIT_REPO/.claude/bugs/test-feature"
mkdir -p "$BUG7_ROOT"
BUG7_DIR="$BUG7_ROOT/TEST-FEATURE-1"
make_bug_dir "$BUG7_DIR"
git -C "$GIT_REPO" add "$BUG7_DIR/bug.json"
git -C "$GIT_REPO" commit -q -m "add bug for t_bug7"

COMMITS_BEFORE="$(git -C "$GIT_REPO" rev-list --count HEAD)"

bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG7_DIR" refused \
    --reason "wontfix" \
    --skip-vet-reason "bypass" \
    > /dev/null 2>&1
T_BUG7_EXIT=$?

COMMITS_AFTER="$(git -C "$GIT_REPO" rev-list --count HEAD 2>/dev/null || echo 0)"

if [ $T_BUG7_EXIT -ne 0 ]; then
    assert_fail "$T_BUG7_LABEL" "bug-status.sh set exited $T_BUG7_EXIT (transition failed; cannot check git commit)"
elif [ "$COMMITS_AFTER" -gt "$COMMITS_BEFORE" ]; then
    assert_pass "$T_BUG7_LABEL"
else
    assert_fail "$T_BUG7_LABEL" "no new git commit after set transition (commits before=$COMMITS_BEFORE, after=$COMMITS_AFTER)"
fi

# ---------------------------------------------------------------------------
# t_bug8: git commit created after file-bug.sh creates a bug
# ---------------------------------------------------------------------------
T_BUG8_LABEL="t_bug8: git commit created after file-bug.sh creates a bug"

BUGS_DIR_GIT="$GIT_REPO/.claude/bugs/test-feature"
mkdir -p "$BUGS_DIR_GIT"

COMMITS_BEFORE_FILE="$(git -C "$GIT_REPO" rev-list --count HEAD)"

# Run file-bug.sh from within the git repo so it uses GIT_REPO as REPO_ROOT
(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature test-feature \
    > /dev/null 2>&1)
T_BUG8_FILE_EXIT=$?

COMMITS_AFTER_FILE="$(git -C "$GIT_REPO" rev-list --count HEAD 2>/dev/null || echo 0)"

if [ $T_BUG8_FILE_EXIT -ne 0 ]; then
    assert_fail "$T_BUG8_LABEL" "file-bug.sh exited $T_BUG8_FILE_EXIT (filing failed; cannot check git commit)"
elif [ "$COMMITS_AFTER_FILE" -gt "$COMMITS_BEFORE_FILE" ]; then
    assert_pass "$T_BUG8_LABEL"
else
    assert_fail "$T_BUG8_LABEL" "no new git commit after file-bug.sh (commits before=$COMMITS_BEFORE_FILE, after=$COMMITS_AFTER_FILE)"
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
