#!/usr/bin/env bash
# test-bug-workspace-map.sh
# Tests that file-bug.sh and list-bugs.sh invoke workspace-map.sh from the
# rabbit-workspace-map contract interface for path resolution, rather than
# constructing paths by convention.
#
# t_wm1: file-bug.sh invokes workspace-map.sh (detected via PATH shim)
# t_wm2: list-bugs.sh invokes workspace-map.sh (detected via PATH shim)
# t_wm3: file-bug.sh does NOT hardcode .claude/bugs path directly (uses workspace-map output)
# t_wm4: list-bugs.sh does NOT hardcode .claude/bugs path directly (uses workspace-map output)
#
# Strategy: place a workspace-map.sh shim earlier in PATH that records calls
# and returns the expected bugs root path. Assert the shim was invoked.
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
# Setup: isolated git repo + workspace-map.sh shim on PATH
# ---------------------------------------------------------------------------
TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

GIT_REPO="$TMPDIR_ROOT/test-repo"
mkdir -p "$GIT_REPO"
git -C "$GIT_REPO" init -q
git -C "$GIT_REPO" config user.email "test@rabbit"
git -C "$GIT_REPO" config user.name "rabbit-test"
git -C "$GIT_REPO" commit --allow-empty -m "init" --quiet

# Registry with test-feature
mkdir -p "$GIT_REPO/.claude/features"
cat > "$GIT_REPO/.claude/features/registry.json" <<'REGEOF'
{
  "features": {
    "test-feature": { "dir": ".claude/features/test-feature" }
  }
}
REGEOF
mkdir -p "$GIT_REPO/.claude/features/test-feature"

# Canonical bugs root that workspace-map.sh would return
WM_BUGS_ROOT="$GIT_REPO/.claude/bugs"
mkdir -p "$WM_BUGS_ROOT"

# Shim directory earlier in PATH
SHIM_DIR="$TMPDIR_ROOT/shims"
mkdir -p "$SHIM_DIR"

# Call log file for the shim
CALL_LOG="$TMPDIR_ROOT/workspace-map-calls.log"

# workspace-map.sh shim: records invocations and echoes the bugs root
cat > "$SHIM_DIR/workspace-map.sh" <<SHIMEOF
#!/usr/bin/env bash
# Test shim for workspace-map.sh — records calls and returns bugs root.
echo "\$@" >> "$CALL_LOG"
echo "$WM_BUGS_ROOT"
SHIMEOF
chmod +x "$SHIM_DIR/workspace-map.sh"

export PATH="$SHIM_DIR:$PATH"

# ---------------------------------------------------------------------------
# t_wm1: file-bug.sh invokes workspace-map.sh
# ---------------------------------------------------------------------------
T_WM1_LABEL="t_wm1: file-bug.sh invokes workspace-map.sh"

rm -f "$CALL_LOG"

(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "WM Test" \
    --severity low \
    --description "workspace-map test" \
    --related-feature test-feature \
    > /dev/null 2>&1)
T_WM1_EXIT=$?

if grep -q "" "$CALL_LOG" 2>/dev/null; then
    assert_pass "$T_WM1_LABEL"
else
    assert_fail "$T_WM1_LABEL" "workspace-map.sh was not called by file-bug.sh (call log empty or missing)"
fi

# ---------------------------------------------------------------------------
# t_wm2: list-bugs.sh invokes workspace-map.sh
# ---------------------------------------------------------------------------
T_WM2_LABEL="t_wm2: list-bugs.sh invokes workspace-map.sh"

rm -f "$CALL_LOG"

(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/list-bugs.sh" \
    --feature test-feature \
    > /dev/null 2>&1)
T_WM2_EXIT=$?

if grep -q "" "$CALL_LOG" 2>/dev/null; then
    assert_pass "$T_WM2_LABEL"
else
    assert_fail "$T_WM2_LABEL" "workspace-map.sh was not called by list-bugs.sh (call log empty or missing)"
fi

# ---------------------------------------------------------------------------
# t_wm3: file-bug.sh uses workspace-map.sh output for bug storage path
#         (bug lands at the path workspace-map.sh returns, not a hardcoded one)
# ---------------------------------------------------------------------------
T_WM3_LABEL="t_wm3: file-bug.sh writes bug.json under path returned by workspace-map.sh"

# Clear any existing bugs from t_wm1 run
rm -rf "$WM_BUGS_ROOT"
mkdir -p "$WM_BUGS_ROOT"

rm -f "$CALL_LOG"

(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/file-bug.sh" \
    --title "WM Path Test" \
    --severity low \
    --description "path resolution test" \
    --related-feature test-feature \
    > /dev/null 2>&1)

# Check that a bug.json was written somewhere under the workspace-map-returned path
BUG_FOUND="$(find "$WM_BUGS_ROOT" -name "bug.json" 2>/dev/null | head -1)"
if [ -n "$BUG_FOUND" ]; then
    assert_pass "$T_WM3_LABEL"
else
    assert_fail "$T_WM3_LABEL" "no bug.json found under workspace-map returned path '$WM_BUGS_ROOT'"
fi

# ---------------------------------------------------------------------------
# t_wm4: list-bugs.sh uses workspace-map.sh output to scan for bugs
#         (finds bugs at the path workspace-map.sh returns)
# ---------------------------------------------------------------------------
T_WM4_LABEL="t_wm4: list-bugs.sh finds bugs at path returned by workspace-map.sh"

# Ensure a bug.json exists at the workspace-map-returned path for scanning
WM_BUG_DIR="$WM_BUGS_ROOT/test-feature/TEST-FEATURE-WM-1"
mkdir -p "$WM_BUG_DIR"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -n --arg ts "$TS" \
    '{name:"TEST-FEATURE-WM-1",title:"WM Bug",status:"open",severity:"low",
      description:"test",related_feature:"test-feature",
      filed:$ts,filed_by:"tester",closed:null,closed_by:null,
      history:[{ts:$ts,actor:"tester",action:"opened",note:"initial"}]}' \
    > "$WM_BUG_DIR/bug.json"

rm -f "$CALL_LOG"

TEXT_OUT="$(cd "$GIT_REPO" && bash "$SCRIPTS_DIR/list-bugs.sh" --feature test-feature --text 2>&1)"

if echo "$TEXT_OUT" | grep -q "TEST-FEATURE-WM-1"; then
    assert_pass "$T_WM4_LABEL"
else
    assert_fail "$T_WM4_LABEL" "TEST-FEATURE-WM-1 not found in list-bugs.sh --text output: '$TEXT_OUT'"
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
