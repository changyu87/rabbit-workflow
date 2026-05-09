#!/bin/bash
# Test: scope-guard blocks edits to a symlink that resolves into a feature dir.
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SCOPE_GUARD="$REPO_ROOT/.claude/hooks/scope-guard.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# FEAT_DIR: the target feature dir (will have the scope marker in t3)
FEAT_DIR="$TMPROOT/feat"
mkdir -p "$FEAT_DIR/artifacts"
echo '{}' > "$FEAT_DIR/feature.json"
echo "canonical content" > "$FEAT_DIR/artifacts/myfile.sh"

# OUTER_DIR: a second feature dir with NO marker — owns the symlink location.
# Without symlink resolution, writes here are denied (no marker in ancestry).
# With symlink resolution, the resolved path is inside FEAT_DIR which has a marker.
OUTER_DIR="$TMPROOT/outer"
mkdir -p "$OUTER_DIR"
echo '{}' > "$OUTER_DIR/feature.json"

SYMLINK="$OUTER_DIR/myfile.sh"
ln -s "$FEAT_DIR/artifacts/myfile.sh" "$SYMLINK"

send_write_event() {
  local path="$1"
  printf '{"tool_name":"Write","tool_input":{"file_path":"%s","content":"x"}}' "$path"
}

# t1: direct write to canonical path inside feature dir is blocked (no marker)
t1() {
  local rc
  send_write_event "$FEAT_DIR/artifacts/myfile.sh" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  [ "$rc" = "2" ] \
    && ok "t1: direct write to canonical feature-dir path blocked (exit 2)" \
    || ko "t1: expected exit 2, got $rc"
}

# t2: write via symlink is blocked — resolved path is inside a feature dir with no marker
t2() {
  local rc
  send_write_event "$SYMLINK" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  [ "$rc" = "2" ] \
    && ok "t2: write via symlink into feature dir blocked (exit 2)" \
    || ko "t2: expected exit 2, got $rc (symlink resolution not implemented or not working)"
}

# t3: write via symlink allowed when the RESOLVED path's ancestor has the scope marker.
# The symlink lives in OUTER_DIR (has feature.json but NO marker → deny without fix).
# The symlink resolves into FEAT_DIR (has feature.json AND marker → allow with fix).
# This test distinguishes whether the guard checks the marker on the resolved path
# vs the symlink's own path.
t3() {
  touch "$FEAT_DIR/.rabbit-scope-active"
  local rc
  send_write_event "$SYMLINK" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  rm -f "$FEAT_DIR/.rabbit-scope-active"
  [ "$rc" = "0" ] \
    && ok "t3: write via symlink allowed when resolved path's ancestor has scope marker (exit 0)" \
    || ko "t3: expected exit 0, got $rc"
}

# t4: write to path outside any feature dir is always allowed
t4() {
  local rc
  send_write_event "$TMPROOT/not-in-any-feature.sh" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  [ "$rc" = "0" ] \
    && ok "t4: write outside feature dir always allowed (exit 0)" \
    || ko "t4: expected exit 0, got $rc"
}

echo "running scope-guard symlink tests"
t1; t2; t3; t4
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
