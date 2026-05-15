#!/usr/bin/env bash
# test-bug-scripts.sh
# Tests t1–t10 for the rabbit-bug feature — centralized storage design.
#
# t1:  scripts/file-bug.sh exists and is executable
# t2:  scripts/bug-status.sh exists and is executable
# t3:  scripts/list-bugs.sh exists and is executable
# t4:  file-bug.sh --related-feature test-feature writes to isolated repo's .claude/bugs/test-feature/TEST-FEATURE-1/bug.json
# t5:  bug.json has status=open, first history entry action=opened, name=TEST-FEATURE-1
# t6:  file-bug.sh --related-feature nonexistent-feature-xyz fails with non-zero exit (registry validation)
# t7:  bug-status.sh set BUG_DIR refused --reason r --skip-vet-reason s --fix-commits abc --touched-files f.sh
#        stores fix_commits and touched_files in history entry
# t8:  description field is unchanged after status transition
# t9:  list-bugs.sh --feature test-feature --text returns the bug created in t4 (scans centralized path)
# t10: feature.json does NOT contain bugs_root key
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
# t1: file-bug.sh exists and is executable
# ---------------------------------------------------------------------------
T1_LABEL="t1: scripts/file-bug.sh exists and is executable"
if [ -f "$SCRIPTS_DIR/file-bug.sh" ] && [ -x "$SCRIPTS_DIR/file-bug.sh" ]; then
    assert_pass "$T1_LABEL"
else
    assert_fail "$T1_LABEL" "file-bug.sh missing or not executable at $SCRIPTS_DIR/file-bug.sh"
fi

# ---------------------------------------------------------------------------
# t2: bug-status.sh exists and is executable
# ---------------------------------------------------------------------------
T2_LABEL="t2: scripts/bug-status.sh exists and is executable"
if [ -f "$SCRIPTS_DIR/bug-status.sh" ] && [ -x "$SCRIPTS_DIR/bug-status.sh" ]; then
    assert_pass "$T2_LABEL"
else
    assert_fail "$T2_LABEL" "bug-status.sh missing or not executable at $SCRIPTS_DIR/bug-status.sh"
fi

# ---------------------------------------------------------------------------
# t3: list-bugs.sh exists and is executable
# ---------------------------------------------------------------------------
T3_LABEL="t3: scripts/list-bugs.sh exists and is executable"
if [ -f "$SCRIPTS_DIR/list-bugs.sh" ] && [ -x "$SCRIPTS_DIR/list-bugs.sh" ]; then
    assert_pass "$T3_LABEL"
else
    assert_fail "$T3_LABEL" "list-bugs.sh missing or not executable at $SCRIPTS_DIR/list-bugs.sh"
fi

# ---------------------------------------------------------------------------
# t4–t9 require file-bug.sh; report FAIL for all if missing
# ---------------------------------------------------------------------------
if [ ! -x "$SCRIPTS_DIR/file-bug.sh" ]; then
    for t in t4 t5 t6 t7 t8 t9; do
        assert_fail "$t" "file-bug.sh not executable — cannot run"
    done
    echo ""
    echo "Results: $pass passed, $fail failed"
    exit 1
fi

# ---------------------------------------------------------------------------
# Isolated git repo setup for t4–t9
# All file-bug.sh / bug-status.sh calls run from inside this isolated repo so
# any git commits land there, not in the live repo.
# ---------------------------------------------------------------------------
ISO_REPO="$(mktemp -d)"
trap 'rm -rf "$ISO_REPO"' EXIT

git -C "$ISO_REPO" init --quiet
git -C "$ISO_REPO" config user.email "test@rabbit"
git -C "$ISO_REPO" config user.name "rabbit-test"
git -C "$ISO_REPO" commit --allow-empty -m "init" --quiet
# Ensure branch is 'main' so file-bug.sh main-branch guard passes
_INIT_BRANCH="$(git -C "$ISO_REPO" branch --show-current 2>/dev/null)"
[ "$_INIT_BRANCH" != "main" ] && git -C "$ISO_REPO" branch -m "$_INIT_BRANCH" main 2>/dev/null || true

# Install find-feature.sh in ISO_REPO so file-bug.sh can call it.
REPO_ROOT_REAL="${RABBIT_ROOT:-$(git -C "$FEATURE_DIR" rev-parse --show-toplevel 2>/dev/null)}"
FIND_FEATURE_SRC="$REPO_ROOT_REAL/.claude/features/contract/scripts/find-feature.sh"
mkdir -p "$ISO_REPO/.claude/features/contract/scripts"
cp "$FIND_FEATURE_SRC" "$ISO_REPO/.claude/features/contract/scripts/find-feature.sh"
cp "$(dirname "$FIND_FEATURE_SRC")/find-feature.py" "$ISO_REPO/.claude/features/contract/scripts/find-feature.py"
chmod +x "$ISO_REPO/.claude/features/contract/scripts/find-feature.sh"

# Create feature.json for test-feature so find-feature.sh can discover it.
mkdir -p "$ISO_REPO/.claude/features/test-feature"
cat > "$ISO_REPO/.claude/features/test-feature/feature.json" <<'FEATEOF'
{
  "name": "test-feature",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "Test feature for bug filing tests."
}
FEATEOF

# ---------------------------------------------------------------------------
# t4: file-bug.sh --related-feature test-feature writes to centralized path
#     inside the isolated repo (.claude/bugs/test-feature/TEST-FEATURE-1/bug.json)
# ---------------------------------------------------------------------------
T4_LABEL="t4: file-bug.sh --related-feature test-feature creates .claude/bugs/test-feature/TEST-FEATURE-1/bug.json"

EXPECTED_BUG_JSON="$ISO_REPO/.claude/bugs/test-feature/TEST-FEATURE-1/bug.json"

(cd "$ISO_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature test-feature \
    > /dev/null 2>&1)
FILE_EXIT=$?

if [ $FILE_EXIT -ne 0 ]; then
    assert_fail "$T4_LABEL" "file-bug.sh exited with code $FILE_EXIT (expected 0)"
elif [ ! -f "$EXPECTED_BUG_JSON" ]; then
    assert_fail "$T4_LABEL" "expected bug.json not found at $EXPECTED_BUG_JSON"
else
    assert_pass "$T4_LABEL"
fi

BUG_JSON="$EXPECTED_BUG_JSON"

# ---------------------------------------------------------------------------
# t5: bug.json has status=open, first history entry action=opened, name=TEST-FEATURE-1
# ---------------------------------------------------------------------------
T5_LABEL="t5: bug.json status=open, first history entry action=opened, name=TEST-FEATURE-1"

if [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T5_LABEL" "no bug.json available (t4 failed)"
else
    STATUS="$(jq -r '.status' "$BUG_JSON" 2>/dev/null)"
    FIRST_ACTION="$(jq -r '.history[0].action' "$BUG_JSON" 2>/dev/null)"
    NAME_VAL="$(jq -r '.name' "$BUG_JSON" 2>/dev/null)"
    if [ "$STATUS" = "open" ] && [ "$FIRST_ACTION" = "opened" ] && [ "$NAME_VAL" = "TEST-FEATURE-1" ]; then
        assert_pass "$T5_LABEL"
    else
        assert_fail "$T5_LABEL" "status=$STATUS (want open), first history action=$FIRST_ACTION (want opened), name=$NAME_VAL (want TEST-FEATURE-1)"
    fi
fi

# ---------------------------------------------------------------------------
# t6: file-bug.sh --related-feature nonexistent-feature-xyz fails (registry validation)
# Run from ISO_REPO so the isolated registry is used.
# ---------------------------------------------------------------------------
T6_LABEL="t6: file-bug.sh --related-feature nonexistent-feature-xyz fails with non-zero exit"

(cd "$ISO_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature nonexistent-feature-xyz \
    > /dev/null 2>&1)
T6_EXIT=$?

if [ $T6_EXIT -ne 0 ]; then
    assert_pass "$T6_LABEL"
else
    assert_fail "$T6_LABEL" "file-bug.sh exited 0 for unknown feature (expected non-zero)"
fi

# ---------------------------------------------------------------------------
# t7: bug-status.sh set BUG_DIR closed --fix-commits abc --touched-files f.sh
#     stores fix_commits and touched_files in history entry.
#     (closed is the valid status for fix_commits; refused rejects fix_commits)
# ---------------------------------------------------------------------------
T7_LABEL="t7: bug-status.sh set closed --fix-commits abc --touched-files f.sh stores those fields in history"

BUG_DIR="$(dirname "${BUG_JSON:-/nonexistent}")"

if [ ! -x "$SCRIPTS_DIR/bug-status.sh" ] || [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T7_LABEL" "bug-status.sh not executable or no bug.json"
else
    bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG_DIR" closed \
        --reason "r" \
        --skip-vet-reason "s" \
        --fix-commits "abc" \
        --touched-files "f.sh" \
        > /dev/null 2>&1
    SET7_EXIT=$?
    if [ $SET7_EXIT -ne 0 ]; then
        assert_fail "$T7_LABEL" "bug-status.sh exited with code $SET7_EXIT"
    else
        FIX_COMMITS="$(jq -r '[.history[] | select(.action=="closed")] | last | .fix_commits // ""' "$BUG_JSON" 2>/dev/null)"
        TOUCHED_FILES="$(jq -r '[.history[] | select(.action=="closed")] | last | .touched_files // ""' "$BUG_JSON" 2>/dev/null)"
        if [ -n "$FIX_COMMITS" ] && [ -n "$TOUCHED_FILES" ]; then
            assert_pass "$T7_LABEL"
        else
            assert_fail "$T7_LABEL" "fix_commits='$FIX_COMMITS' touched_files='$TOUCHED_FILES' (both must be non-empty)"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# t8: description field unchanged after status transition
# ---------------------------------------------------------------------------
T8_LABEL="t8: description field unchanged after status transitions"

if [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T8_LABEL" "no bug.json available"
else
    DESC_NOW="$(jq -r '.description' "$BUG_JSON" 2>/dev/null)"
    if [ "$DESC_NOW" = "D" ]; then
        assert_pass "$T8_LABEL"
    else
        assert_fail "$T8_LABEL" "description changed: got '$DESC_NOW' (want 'D')"
    fi
fi

# ---------------------------------------------------------------------------
# t9: list-bugs.sh --feature test-feature --text returns the bug from t4
#     Run from ISO_REPO so list-bugs.sh resolves REPO_ROOT to the isolated repo.
# ---------------------------------------------------------------------------
T9_LABEL="t9: list-bugs.sh --feature test-feature --text returns bug created in t4"

if [ ! -x "$SCRIPTS_DIR/list-bugs.sh" ] || [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T9_LABEL" "list-bugs.sh not executable or no bug.json"
else
    BUG_NAME="$(jq -r '.name' "$BUG_JSON" 2>/dev/null)"
    TEXT_OUT="$(cd "$ISO_REPO" && bash "$SCRIPTS_DIR/list-bugs.sh" --feature test-feature --text 2>&1)"
    LIST_EXIT=$?
    if [ $LIST_EXIT -ne 0 ]; then
        assert_fail "$T9_LABEL" "list-bugs.sh exited with code $LIST_EXIT"
    elif echo "$TEXT_OUT" | grep -q "$BUG_NAME"; then
        assert_pass "$T9_LABEL"
    else
        assert_fail "$T9_LABEL" "bug name '$BUG_NAME' not found in --text output: $(echo "$TEXT_OUT" | head -c 300)"
    fi
fi

# ---------------------------------------------------------------------------
# t11: list-bugs.sh --text output includes severity in [SEVERITY] format
# ---------------------------------------------------------------------------
T11_LABEL="t11: list-bugs.sh --text output includes [SEVERITY] field"

if [ ! -x "$SCRIPTS_DIR/list-bugs.sh" ] || [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T11_LABEL" "list-bugs.sh not executable or no bug.json"
else
    SEVERITY_VAL="$(jq -r '.severity' "$BUG_JSON" 2>/dev/null)"
    TEXT_OUT11="$(cd "$ISO_REPO" && bash "$SCRIPTS_DIR/list-bugs.sh" --feature test-feature --text 2>&1)"
    LIST11_EXIT=$?
    if [ $LIST11_EXIT -ne 0 ]; then
        assert_fail "$T11_LABEL" "list-bugs.sh exited with code $LIST11_EXIT"
    elif echo "$TEXT_OUT11" | grep -qF "[$SEVERITY_VAL]"; then
        assert_pass "$T11_LABEL"
    else
        assert_fail "$T11_LABEL" "severity '[$SEVERITY_VAL]' not found in --text output: $(echo "$TEXT_OUT11" | head -c 300)"
    fi
fi

# ---------------------------------------------------------------------------
# t10: feature.json does NOT contain bugs_root key
# ---------------------------------------------------------------------------
T10_LABEL="t10: feature.json does NOT contain bugs_root key"

FEAT_JSON="$FEATURE_DIR/feature.json"
if [ ! -f "$FEAT_JSON" ]; then
    assert_fail "$T10_LABEL" "feature.json not found at $FEAT_JSON"
else
    BUGS_ROOT_VAL="$(jq -r '.bugs_root // "ABSENT"' "$FEAT_JSON" 2>/dev/null)"
    if [ "$BUGS_ROOT_VAL" = "ABSENT" ] || [ "$BUGS_ROOT_VAL" = "null" ]; then
        assert_pass "$T10_LABEL"
    else
        assert_fail "$T10_LABEL" "bugs_root is still present in feature.json: '$BUGS_ROOT_VAL'"
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
