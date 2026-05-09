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

FEAT_DIR="$TMPROOT/feat"
mkdir -p "$FEAT_DIR/artifacts"
echo '{}' > "$FEAT_DIR/feature.json"
echo "canonical content" > "$FEAT_DIR/artifacts/myfile.sh"

SYMLINK="$TMPROOT/myfile.sh"
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

# t2: write via symlink is also blocked when scope-guard resolves symlinks
t2() {
  local rc
  send_write_event "$SYMLINK" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  [ "$rc" = "2" ] \
    && ok "t2: write via symlink into feature dir blocked (exit 2)" \
    || ko "t2: expected exit 2, got $rc (symlink resolution not yet implemented)"
}

# t3: write via symlink allowed when scope marker present
t3() {
  touch "$FEAT_DIR/.rabbit-scope-active"
  local rc
  send_write_event "$SYMLINK" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  rm -f "$FEAT_DIR/.rabbit-scope-active"
  [ "$rc" = "0" ] \
    && ok "t3: write via symlink allowed when scope marker present (exit 0)" \
    || ko "t3: expected exit 0, got $rc"
}

# t4: write to path outside any feature dir always allowed
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
