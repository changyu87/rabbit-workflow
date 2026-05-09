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

# mkbug <prefix> — files a bug and returns the path to its bug dir.
mkbug() {
  local prefix="$1"
  local out; out=$("$FILE_BUG" --related-feature "$prefix" --title "t" --severity low --description "d" 2>/dev/null)
  # stdout: "filed: <path>  [<NAME>]"
  echo "$out" | sed -E 's/^filed: ([^ ]+) .*/\1/' | xargs dirname
}

run() { "$STATUS" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# s1: read status of an open bug
s1() {
  local dir; dir=$(mkbug "status-s1")
  local rc; rc=$(run get "$dir")
  [ "$rc" = "0" ] && [ "$(cat "$TMPROOT/stdout")" = "open" ] \
    && ok "s1: get returns open" \
    || ko "s1: rc=$rc out='$(cat "$TMPROOT/stdout")'"
}

# s2: open -> closed succeeds
s2() {
  local dir; dir=$(mkbug "status-s2")
  local rc; rc=$(run set "$dir" closed --note "fixed in #42")
  local s; s=$(jq -r '.status' "$dir/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && ok "s2: open -> closed succeeds" \
    || ko "s2: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s3: closed -> reopened succeeds
s3() {
  local dir; dir=$(mkbug "status-s3")
  run set "$dir" closed --note "first close" >/dev/null
  local rc; rc=$(run set "$dir" reopened --note "regression")
  local s; s=$(jq -r '.status' "$dir/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "reopened" ] \
    && ok "s3: closed -> reopened succeeds" \
    || ko "s3: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s4: reopened -> closed succeeds
s4() {
  local dir; dir=$(mkbug "status-s4")
  run set "$dir" closed --note "x" >/dev/null
  run set "$dir" reopened --note "y" >/dev/null
  local rc; rc=$(run set "$dir" closed --note "second close")
  local s; s=$(jq -r '.status' "$dir/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && ok "s4: reopened -> closed succeeds" \
    || ko "s4: rc=$rc s=$s"
}

# s5: closed -> open denied (must use 'reopened')
s5() {
  local dir; dir=$(mkbug "status-s5")
  run set "$dir" closed --note "x" >/dev/null
  local rc; rc=$(run set "$dir" open --note "wrong way")
  local s; s=$(jq -r '.status' "$dir/bug.json")
  [ "$rc" != "0" ] && [ "$s" = "closed" ] \
    && ok "s5: closed -> open denied (use reopened)" \
    || ko "s5: rc=$rc s=$s"
}

# s6: invalid target status rejected
s6() {
  local dir; dir=$(mkbug "status-s6")
  local rc; rc=$(run set "$dir" weird --note "x")
  [ "$rc" != "0" ] && ok "s6: invalid status rejected" || ko "s6: rc=$rc"
}

# s7: setting same status is a no-op (allowed but not history-spammed twice)
s7() {
  local dir; dir=$(mkbug "status-s7")
  local rc; rc=$(run set "$dir" open --note "redundant")
  local len; len=$(jq '.history | length' "$dir/bug.json")
  [ "$rc" = "0" ] && [ "$len" = "1" ] \
    && ok "s7: same-status set is no-op (history len=1)" \
    || ko "s7: rc=$rc history len=$len"
}

# s8: history grows on each transition
s8() {
  local dir; dir=$(mkbug "status-s8")
  run set "$dir" closed --note "a" >/dev/null
  run set "$dir" reopened --note "b" >/dev/null
  run set "$dir" closed --note "c" >/dev/null
  local len; len=$(jq '.history | length' "$dir/bug.json")
  [ "$len" = "4" ] \
    && ok "s8: history len=4 (open + 3 transitions)" \
    || ko "s8: history len=$len (expected 4)"
}

# s9: missing bug dir errors with clear message
s9() {
  local rc; rc=$(run get "$BUG_ROOT/does-not-exist")
  [ "$rc" != "0" ] && ok "s9: missing bug dir errors" || ko "s9: rc=$rc"
}

# bdir <prefix> — returns the bug directory for a bug filed under prefix (by mkbug)
bdir() {
  local prefix="$1"
  ls -dt "$BUG_ROOT/${prefix^^}"-* 2>/dev/null | head -1
}

# s14: open -> refused succeeds
s14() {
  mkbug ts14
  local rc; rc=$(run set "$(bdir ts14)" refused --note "by design")
  local s; s=$(jq -r '.status' "$(bdir ts14)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "refused" ] \
    && ok "s14: open -> refused succeeds" \
    || ko "s14: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s15: reopened -> refused succeeds
s15() {
  mkbug ts15
  echo '{}' > "$(bdir ts15)/vet-triage.json"
  run set "$(bdir ts15)" closed --note "first close" >/dev/null
  run set "$(bdir ts15)" reopened --note "regression" >/dev/null
  local rc; rc=$(run set "$(bdir ts15)" refused --note "still by design")
  local s; s=$(jq -r '.status' "$(bdir ts15)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "refused" ] \
    && ok "s15: reopened -> refused succeeds" \
    || ko "s15: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s16: refused -> open denied
s16() {
  mkbug ts16
  run set "$(bdir ts16)" refused --note "by design" >/dev/null
  local rc; rc=$(run set "$(bdir ts16)" open --note "try reopen")
  local s; s=$(jq -r '.status' "$(bdir ts16)/bug.json")
  [ "$rc" != "0" ] && [ "$s" = "refused" ] \
    && ok "s16: refused -> open denied" \
    || ko "s16: rc=$rc s=$s"
}

# s17: refused -> closed denied (must use reopened first)
s17() {
  mkbug ts17
  run set "$(bdir ts17)" refused --note "by design" >/dev/null
  local rc; rc=$(run set "$(bdir ts17)" closed --note "try close")
  local s; s=$(jq -r '.status' "$(bdir ts17)/bug.json")
  [ "$rc" = "1" ] && [ "$s" = "refused" ] \
    && ok "s17: refused -> closed denied (must use reopened)" \
    || ko "s17: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s18: refused -> refused is a no-op
s18() {
  mkbug ts18
  run set "$(bdir ts18)" refused --note "by design" >/dev/null
  local rc; rc=$(run set "$(bdir ts18)" refused --note "redundant")
  local len; len=$(jq '.history | length' "$(bdir ts18)/bug.json")
  [ "$rc" = "0" ] && [ "$len" = "2" ] \
    && ok "s18: refused -> refused no-op (history len=2)" \
    || ko "s18: rc=$rc history len=$len"
}

# s19: refused -> reopened allowed (to revive)
s19() {
  mkbug ts19
  run set "$(bdir ts19)" refused --note "by design" >/dev/null
  local rc; rc=$(run set "$(bdir ts19)" reopened --note "reconsidered")
  local s; s=$(jq -r '.status' "$(bdir ts19)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "reopened" ] \
    && ok "s19: refused -> reopened allowed" \
    || ko "s19: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s20: list-bugs --status refused returns the bug
s20() {
  mkbug ts20
  run set "$(bdir ts20)" refused --note "by design" >/dev/null
  local result
  result=$(BUG_ROOT="$BUG_ROOT" bash "$(dirname "$STATUS")/../scripts/list-bugs.sh" --status refused 2>/dev/null)
  echo "$result" | grep -q "TS20" \
    && ok "s20: list-bugs --status refused returns refused bugs" \
    || ko "s20: result='$result'"
}

echo "running bug-status tests against $STATUS"
s1; s2; s3; s4; s5; s6; s7; s8; s9; s14; s15; s16; s17; s18; s19; s20
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
