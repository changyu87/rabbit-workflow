#!/usr/bin/env bash
# test-bug-git-isolation.sh
# Regression tests for RABBIT-BUG-4: tests use ISO_REPO to keep live repo clean.
#
# t_iso1: file-bug.sh run from ISO_REPO does NOT commit to the live repo,
#         AND DOES commit to ISO_REPO (audit trail works).
# t_iso2: bug-status.sh run from ISO_REPO does NOT commit to the live repo,
#         AND DOES commit to ISO_REPO (audit trail works).
#
# These tests PASS when the ISO_REPO pattern is in effect (tests use mktemp
# isolated repos). They would FAIL if someone reverted tests to run against
# the live repo directly.
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
# ISO_REPO setup: a fresh git repo separate from the live repo.
# Scripts run (cd ISO_REPO && ...) so their git discovery lands here,
# not in the live repo.
# ---------------------------------------------------------------------------
ISO_REPO="$(mktemp -d)"
trap 'rm -rf "$ISO_REPO"' EXIT

git -C "$ISO_REPO" init --quiet
git -C "$ISO_REPO" config user.email "test@rabbit"
git -C "$ISO_REPO" config user.name "rabbit-test"
git -C "$ISO_REPO" commit --allow-empty -m "init" --quiet

# Minimal registry with test-feature so registry validation passes.
mkdir -p "$ISO_REPO/.claude/features/test-feature"
cat > "$ISO_REPO/.claude/features/registry.json" <<'REGEOF'
{
  "features": {
    "test-feature": { "dir": ".claude/features/test-feature" }
  }
}
REGEOF
cat > "$ISO_REPO/.claude/features/test-feature/feature.json" <<'FEATEOF'
{"name":"test-feature","owner":"tester","version":"1.0"}
FEATEOF

# ---------------------------------------------------------------------------
# t_iso1: file-bug.sh run from ISO_REPO
#   - live repo commit count must NOT increase
#   - ISO_REPO commit count must increase by 1 (audit trail)
# ---------------------------------------------------------------------------
T_ISO1_LABEL="t_iso1: file-bug.sh (ISO_REPO) keeps live repo clean AND commits in ISO_REPO"

LIVE_BEFORE="$(git -C "$REPO_ROOT" rev-list --count HEAD)"
ISO_BEFORE="$(git -C "$ISO_REPO" rev-list --count HEAD)"

(cd "$ISO_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "Isolation Probe" \
    --severity low \
    --description "ISO_REPO isolation test" \
    --related-feature test-feature \
    > /dev/null 2>&1)
FILE_EXIT=$?

LIVE_AFTER="$(git -C "$REPO_ROOT" rev-list --count HEAD)"
ISO_AFTER="$(git -C "$ISO_REPO" rev-list --count HEAD)"

if [ $FILE_EXIT -ne 0 ]; then
    assert_fail "$T_ISO1_LABEL" "file-bug.sh exited $FILE_EXIT; cannot confirm isolation"
elif [ "$LIVE_AFTER" -gt "$LIVE_BEFORE" ]; then
    assert_fail "$T_ISO1_LABEL" \
        "live repo gained commit(s): before=$LIVE_BEFORE after=$LIVE_AFTER — script polluted live repo"
elif [ "$ISO_AFTER" -le "$ISO_BEFORE" ]; then
    assert_fail "$T_ISO1_LABEL" \
        "ISO_REPO commit count did not increase: before=$ISO_BEFORE after=$ISO_AFTER — audit trail broken"
else
    assert_pass "$T_ISO1_LABEL"
fi

# ---------------------------------------------------------------------------
# t_iso2: bug-status.sh run from ISO_REPO
#   - live repo commit count must NOT increase
#   - ISO_REPO commit count must increase by 1 (audit trail)
# ---------------------------------------------------------------------------
T_ISO2_LABEL="t_iso2: bug-status.sh (ISO_REPO) keeps live repo clean AND commits in ISO_REPO"

# Create a bug.json in ISO_REPO to transition
BUG_DIR="$ISO_REPO/.claude/bugs/test-feature/TEST-FEATURE-ISO2"
mkdir -p "$BUG_DIR"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -n \
    --arg ts "$TS" \
    '{name:"TEST-FEATURE-ISO2",title:"ISO2 Test",status:"open",severity:"low",
      description:"isolation test",related_feature:"test-feature",
      filed:$ts,filed_by:"tester",closed:null,closed_by:null,
      history:[{ts:$ts,actor:"tester",action:"opened",note:"initial filing"}]}' \
    > "$BUG_DIR/bug.json"

LIVE_BEFORE2="$(git -C "$REPO_ROOT" rev-list --count HEAD)"
ISO_BEFORE2="$(git -C "$ISO_REPO" rev-list --count HEAD)"

(cd "$ISO_REPO" && bash "$SCRIPTS_DIR/bug-status.sh" set "$BUG_DIR" refused \
    --reason "isolation probe" \
    --skip-vet-reason "test" \
    > /dev/null 2>&1)
SET_EXIT=$?

LIVE_AFTER2="$(git -C "$REPO_ROOT" rev-list --count HEAD)"
ISO_AFTER2="$(git -C "$ISO_REPO" rev-list --count HEAD)"

if [ $SET_EXIT -ne 0 ]; then
    assert_fail "$T_ISO2_LABEL" "bug-status.sh set exited $SET_EXIT; cannot confirm isolation"
elif [ "$LIVE_AFTER2" -gt "$LIVE_BEFORE2" ]; then
    assert_fail "$T_ISO2_LABEL" \
        "live repo gained commit(s): before=$LIVE_BEFORE2 after=$LIVE_AFTER2 — script polluted live repo"
elif [ "$ISO_AFTER2" -le "$ISO_BEFORE2" ]; then
    assert_fail "$T_ISO2_LABEL" \
        "ISO_REPO commit count did not increase: before=$ISO_BEFORE2 after=$ISO_AFTER2 — audit trail broken"
else
    assert_pass "$T_ISO2_LABEL"
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
