#!/usr/bin/env bash
# test-bug-scripts.sh
# Tests t1–t10 for the rabbit-bug feature — centralized storage design.
#
# t1:  scripts/file-bug.sh exists and is executable
# t2:  scripts/bug-status.sh exists and is executable
# t3:  scripts/list-bugs.sh exists and is executable
# t4:  file-bug.sh --related-feature rabbit-bug writes to .claude/bugs/rabbit-bug/RABBIT-BUG-1/bug.json
# t5:  bug.json has status=open, first history entry action=opened, name=RABBIT-BUG-1
# t6:  file-bug.sh --related-feature nonexistent-feature-xyz fails with non-zero exit (registry validation)
# t7:  bug-status.sh set BUG_DIR refused --note r --skip-vet-reason s --fix-commits abc --touched-files f.sh
#        stores fix_commits and touched_files in history entry
# t8:  description field is unchanged after status transition
# t9:  list-bugs.sh --feature rabbit-bug --text returns the bug created in t4 (scans centralized path)
# t10: feature.json does NOT contain bugs_root key
#
# Exit: 1 if any assertion fails.

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$FEATURE_DIR/scripts"
REPO_ROOT="$(git -C "$FEATURE_DIR" rev-parse --show-toplevel)"

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
# t4: file-bug.sh --related-feature rabbit-bug writes to centralized path
#     .claude/bugs/rabbit-bug/RABBIT-BUG-<N>/bug.json
#     (NOT inside any feature directory)
# ---------------------------------------------------------------------------
T4_LABEL="t4: file-bug.sh --related-feature rabbit-bug creates .claude/bugs/rabbit-bug/RABBIT-BUG-1/bug.json"

CENTRALIZED_BUGS_ROOT="$REPO_ROOT/.claude/bugs"
EXPECTED_FEATURE_BUG_DIR="$CENTRALIZED_BUGS_ROOT/rabbit-bug"

# Clean up any prior test artifact so numbering starts at 1
rm -rf "$EXPECTED_FEATURE_BUG_DIR/RABBIT-BUG-1"

bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature rabbit-bug \
    > /dev/null 2>&1
FILE_EXIT=$?

EXPECTED_BUG_JSON="$EXPECTED_FEATURE_BUG_DIR/RABBIT-BUG-1/bug.json"

if [ $FILE_EXIT -ne 0 ]; then
    assert_fail "$T4_LABEL" "file-bug.sh exited with code $FILE_EXIT (expected 0)"
elif [ ! -f "$EXPECTED_BUG_JSON" ]; then
    assert_fail "$T4_LABEL" "expected bug.json not found at $EXPECTED_BUG_JSON"
else
    assert_pass "$T4_LABEL"
fi

BUG_JSON="$EXPECTED_BUG_JSON"

# ---------------------------------------------------------------------------
# t5: bug.json has status=open, first history entry action=opened, name=RABBIT-BUG-1
# ---------------------------------------------------------------------------
T5_LABEL="t5: bug.json status=open, first history entry action=opened, name=RABBIT-BUG-1"

if [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T5_LABEL" "no bug.json available (t4 failed)"
else
    STATUS="$(jq -r '.status' "$BUG_JSON" 2>/dev/null)"
    FIRST_ACTION="$(jq -r '.history[0].action' "$BUG_JSON" 2>/dev/null)"
    NAME_VAL="$(jq -r '.name' "$BUG_JSON" 2>/dev/null)"
    if [ "$STATUS" = "open" ] && [ "$FIRST_ACTION" = "opened" ] && [ "$NAME_VAL" = "RABBIT-BUG-1" ]; then
        assert_pass "$T5_LABEL"
    else
        assert_fail "$T5_LABEL" "status=$STATUS (want open), first history action=$FIRST_ACTION (want opened), name=$NAME_VAL (want RABBIT-BUG-1)"
    fi
fi

# ---------------------------------------------------------------------------
# t6: file-bug.sh --related-feature nonexistent-feature-xyz fails (registry validation)
# ---------------------------------------------------------------------------
T6_LABEL="t6: file-bug.sh --related-feature nonexistent-feature-xyz fails with non-zero exit"

bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "T" \
    --severity low \
    --description "D" \
    --related-feature nonexistent-feature-xyz \
    > /dev/null 2>&1
T6_EXIT=$?

if [ $T6_EXIT -ne 0 ]; then
    assert_pass "$T6_LABEL"
else
    assert_fail "$T6_LABEL" "file-bug.sh exited 0 for unknown feature (expected non-zero)"
fi

# ---------------------------------------------------------------------------
# t7: bug-status.sh set BUG_DIR refused stores fix_commits and touched_files
# ---------------------------------------------------------------------------
T7_LABEL="t7: bug-status.sh set refused --fix-commits abc --touched-files f.sh stores those fields in history"

BUG_DIR="$(dirname "${BUG_JSON:-/nonexistent}")"

if [ ! -x "$SCRIPTS_DIR/bug-status.sh" ] || [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T7_LABEL" "bug-status.sh not executable or no bug.json"
else
    bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG_DIR" refused \
        --note "r" \
        --skip-vet-reason "s" \
        --fix-commits "abc" \
        --touched-files "f.sh" \
        > /dev/null 2>&1
    SET7_EXIT=$?
    if [ $SET7_EXIT -ne 0 ]; then
        assert_fail "$T7_LABEL" "bug-status.sh exited with code $SET7_EXIT"
    else
        FIX_COMMITS="$(jq -r '[.history[] | select(.action=="refused")] | last | .fix_commits // ""' "$BUG_JSON" 2>/dev/null)"
        TOUCHED_FILES="$(jq -r '[.history[] | select(.action=="refused")] | last | .touched_files // ""' "$BUG_JSON" 2>/dev/null)"
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
# t9: list-bugs.sh --feature rabbit-bug --text returns the bug from t4
#     (must scan centralized path .claude/bugs/rabbit-bug/, not feature.json bugs_root)
# ---------------------------------------------------------------------------
T9_LABEL="t9: list-bugs.sh --feature rabbit-bug --text returns bug created in t4"

if [ ! -x "$SCRIPTS_DIR/list-bugs.sh" ] || [ ! -f "$BUG_JSON" ]; then
    assert_fail "$T9_LABEL" "list-bugs.sh not executable or no bug.json"
else
    BUG_NAME="$(jq -r '.name' "$BUG_JSON" 2>/dev/null)"
    TEXT_OUT="$(bash "$SCRIPTS_DIR/list-bugs.sh" --feature rabbit-bug --text 2>&1)"
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
