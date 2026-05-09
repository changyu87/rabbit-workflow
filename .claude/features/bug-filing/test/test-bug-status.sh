#!/bin/bash
# End-to-end tests for bug-status.sh.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FILE_BUG="$FEATURE_DIR/scripts/file-bug.sh"
STATUS="$FEATURE_DIR/scripts/bug-status.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

export BUG_ROOT="$TMPROOT/bugs"
mkdir -p "$BUG_ROOT"

mkbug() {
  "$FILE_BUG" --name "$1" --title "t" --severity low --description "d" >/dev/null
}

run() { "$STATUS" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# s1: read status of an open bug
s1() {
  mkbug "2026-05-08-s1"
  local rc; rc=$(run get "$BUG_ROOT/2026-05-08-s1")
  [ "$rc" = "0" ] && [ "$(cat "$TMPROOT/stdout")" = "open" ] \
    && ok "s1: get returns open" \
    || ko "s1: rc=$rc out='$(cat "$TMPROOT/stdout")'"
}

# s2: open -> closed succeeds
s2() {
  mkbug "2026-05-08-s2"
  local rc; rc=$(run set "$BUG_ROOT/2026-05-08-s2" closed --note "fixed in #42")
  local s; s=$(jq -r '.status' "$BUG_ROOT/2026-05-08-s2/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && ok "s2: open -> closed succeeds" \
    || ko "s2: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s3: closed -> reopened succeeds
s3() {
  mkbug "2026-05-08-s3"
  run set "$BUG_ROOT/2026-05-08-s3" closed --note "first close" >/dev/null
  local rc; rc=$(run set "$BUG_ROOT/2026-05-08-s3" reopened --note "regression")
  local s; s=$(jq -r '.status' "$BUG_ROOT/2026-05-08-s3/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "reopened" ] \
    && ok "s3: closed -> reopened succeeds" \
    || ko "s3: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s4: reopened -> closed succeeds
s4() {
  mkbug "2026-05-08-s4"
  run set "$BUG_ROOT/2026-05-08-s4" closed --note "x" >/dev/null
  run set "$BUG_ROOT/2026-05-08-s4" reopened --note "y" >/dev/null
  local rc; rc=$(run set "$BUG_ROOT/2026-05-08-s4" closed --note "second close")
  local s; s=$(jq -r '.status' "$BUG_ROOT/2026-05-08-s4/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && ok "s4: reopened -> closed succeeds" \
    || ko "s4: rc=$rc s=$s"
}

# s5: closed -> open denied (must use 'reopened')
s5() {
  mkbug "2026-05-08-s5"
  run set "$BUG_ROOT/2026-05-08-s5" closed --note "x" >/dev/null
  local rc; rc=$(run set "$BUG_ROOT/2026-05-08-s5" open --note "wrong way")
  local s; s=$(jq -r '.status' "$BUG_ROOT/2026-05-08-s5/bug.json")
  [ "$rc" != "0" ] && [ "$s" = "closed" ] \
    && ok "s5: closed -> open denied (use reopened)" \
    || ko "s5: rc=$rc s=$s"
}

# s6: invalid target status rejected
s6() {
  mkbug "2026-05-08-s6"
  local rc; rc=$(run set "$BUG_ROOT/2026-05-08-s6" weird --note "x")
  [ "$rc" != "0" ] && ok "s6: invalid status rejected" || ko "s6: rc=$rc"
}

# s7: setting same status is a no-op (allowed but not history-spammed twice)
s7() {
  mkbug "2026-05-08-s7"
  local rc; rc=$(run set "$BUG_ROOT/2026-05-08-s7" open --note "redundant")
  local len; len=$(jq '.history | length' "$BUG_ROOT/2026-05-08-s7/bug.json")
  [ "$rc" = "0" ] && [ "$len" = "1" ] \
    && ok "s7: same-status set is no-op (history len=1)" \
    || ko "s7: rc=$rc history len=$len"
}

# s8: history grows on each transition
s8() {
  mkbug "2026-05-08-s8"
  run set "$BUG_ROOT/2026-05-08-s8" closed --note "a" >/dev/null
  run set "$BUG_ROOT/2026-05-08-s8" reopened --note "b" >/dev/null
  run set "$BUG_ROOT/2026-05-08-s8" closed --note "c" >/dev/null
  local len; len=$(jq '.history | length' "$BUG_ROOT/2026-05-08-s8/bug.json")
  [ "$len" = "4" ] \
    && ok "s8: history len=4 (open + 3 transitions)" \
    || ko "s8: history len=$len (expected 4)"
}

# s9: missing bug dir errors with clear message
s9() {
  local rc; rc=$(run get "$BUG_ROOT/does-not-exist")
  [ "$rc" != "0" ] && ok "s9: missing bug dir errors" || ko "s9: rc=$rc"
}

echo "running bug-status tests against $STATUS"
s1; s2; s3; s4; s5; s6; s7; s8; s9
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
