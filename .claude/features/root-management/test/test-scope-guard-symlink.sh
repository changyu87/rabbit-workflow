#!/bin/bash
# Test: scope-guard v2 behavior — default-deny inside repo root, allow outside.
#
# v2 scope model:
#   1. Outside repo root            -> ALLOW
#   2. Basename is .rabbit-scope-active -> ALLOW (always exempt)
#   3. Basename in allowlist (settings.json, settings.local.json, .gitignore) -> ALLOW
#   4. .rabbit-scope-active found in ancestor chain -> ALLOW
#   5. Default                      -> DENY (exit 2)
#
# Old symlink-resolution tests (v1 feature-dir detection) are replaced here
# because v2 guards by repo root, not by feature.json presence.
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SCOPE_GUARD="$REPO_ROOT/.claude/hooks/scope-guard.sh"

# Temp dir INSIDE the repo so scope-guard v2 actually guards it.
TMPROOT="$REPO_ROOT/.tmp-sgtest-$$"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

send_write_event() {
  local path="$1"
  printf '{"tool_name":"Write","tool_input":{"file_path":"%s","content":"x"}}' "$path"
}

# t1: Write to a path inside the repo root (no scope marker) -> exit 2 (deny)
t1() {
  mkdir -p "$TMPROOT"
  local target="$TMPROOT/somefile.txt"
  local rc
  send_write_event "$target" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  [ "$rc" = "2" ] \
    && ok "t1: write inside repo root with no scope marker denied (exit 2)" \
    || ko "t1: expected exit 2, got $rc"
}

# t2: Write to an allowlisted filename inside the repo root -> exit 0 (allow)
t2() {
  mkdir -p "$TMPROOT"
  local target="$TMPROOT/settings.json"
  local rc
  send_write_event "$target" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  [ "$rc" = "0" ] \
    && ok "t2: write to allowlisted filename (settings.json) allowed (exit 0)" \
    || ko "t2: expected exit 0, got $rc"
}

# t3: Write to a path inside the repo root WITH .rabbit-scope-active in ancestor -> exit 0 (allow)
t3() {
  mkdir -p "$TMPROOT"
  touch "$TMPROOT/.rabbit-scope-active"
  local target="$TMPROOT/somefile.txt"
  local rc
  send_write_event "$target" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  rm -f "$TMPROOT/.rabbit-scope-active"
  [ "$rc" = "0" ] \
    && ok "t3: write inside repo root with scope marker in ancestor allowed (exit 0)" \
    || ko "t3: expected exit 0, got $rc"
}

# t4: Write to a path OUTSIDE the repo root -> exit 0 (allow)
t4() {
  local outside; outside="$(mktemp)"
  local rc
  send_write_event "$outside" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  rm -f "$outside"
  [ "$rc" = "0" ] \
    && ok "t4: write outside repo root always allowed (exit 0)" \
    || ko "t4: expected exit 0, got $rc"
}

# t5: Write to .rabbit-scope-active itself (anywhere in repo) -> exit 0 (always exempt)
t5() {
  mkdir -p "$TMPROOT"
  local target="$TMPROOT/.rabbit-scope-active"
  local rc
  send_write_event "$target" | bash "$SCOPE_GUARD" >/dev/null 2>&1
  rc=$?
  [ "$rc" = "0" ] \
    && ok "t5: write to .rabbit-scope-active itself is always exempt (exit 0)" \
    || ko "t5: expected exit 0, got $rc"
}

echo "running scope-guard v2 tests"
t1; t2; t3; t4; t5
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
