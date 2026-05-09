#!/bin/bash
# End-to-end tests for bug-status.sh (updated for FEATURE-N naming + vet gate).
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

# Each test uses a unique prefix so counters never collide.
mkbug() {
  local prefix="$1"
  "$FILE_BUG" --related-feature "$prefix" --title "t" --severity low --description "d" >/dev/null
}
bdir() { echo "$BUG_ROOT/${1^^}-1"; }

run() { "$STATUS" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# s1: get returns open
s1() {
  mkbug ts1
  local rc; rc=$(run get "$(bdir ts1)")
  [ "$rc" = "0" ] && [ "$(cat "$TMPROOT/stdout")" = "open" ] \
    && ok "s1: get returns open" \
    || ko "s1: rc=$rc out='$(cat "$TMPROOT/stdout")'"
}

# s2: open -> closed succeeds (with vet-triage.json)
s2() {
  mkbug ts2
  echo '{}' > "$(bdir ts2)/vet-triage.json"
  local rc; rc=$(run set "$(bdir ts2)" closed --note "fixed")
  local s; s=$(jq -r '.status' "$(bdir ts2)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && ok "s2: open -> closed succeeds" \
    || ko "s2: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s3: closed -> reopened succeeds
s3() {
  mkbug ts3
  echo '{}' > "$(bdir ts3)/vet-triage.json"
  run set "$(bdir ts3)" closed --note "first close" >/dev/null
  local rc; rc=$(run set "$(bdir ts3)" reopened --note "regression")
  local s; s=$(jq -r '.status' "$(bdir ts3)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "reopened" ] \
    && ok "s3: closed -> reopened succeeds" \
    || ko "s3: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s4: reopened -> closed succeeds (with vet-triage.json)
s4() {
  mkbug ts4
  echo '{}' > "$(bdir ts4)/vet-triage.json"
  run set "$(bdir ts4)" closed --note "x" >/dev/null
  run set "$(bdir ts4)" reopened --note "y" >/dev/null
  local rc; rc=$(run set "$(bdir ts4)" closed --note "second close")
  local s; s=$(jq -r '.status' "$(bdir ts4)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && ok "s4: reopened -> closed succeeds" \
    || ko "s4: rc=$rc s=$s"
}

# s5: closed -> open denied
s5() {
  mkbug ts5
  echo '{}' > "$(bdir ts5)/vet-triage.json"
  run set "$(bdir ts5)" closed --note "x" >/dev/null
  local rc; rc=$(run set "$(bdir ts5)" open --note "wrong way")
  local s; s=$(jq -r '.status' "$(bdir ts5)/bug.json")
  [ "$rc" != "0" ] && [ "$s" = "closed" ] \
    && ok "s5: closed -> open denied" \
    || ko "s5: rc=$rc s=$s"
}

# s6: invalid status rejected
s6() {
  mkbug ts6
  local rc; rc=$(run set "$(bdir ts6)" weird --note "x")
  [ "$rc" != "0" ] && ok "s6: invalid status rejected" || ko "s6: rc=$rc"
}

# s7: same-status is no-op
s7() {
  mkbug ts7
  local rc; rc=$(run set "$(bdir ts7)" open --note "redundant")
  local len; len=$(jq '.history | length' "$(bdir ts7)/bug.json")
  [ "$rc" = "0" ] && [ "$len" = "1" ] \
    && ok "s7: same-status no-op (history len=1)" \
    || ko "s7: rc=$rc history len=$len"
}

# s8: history grows on each transition
s8() {
  mkbug ts8
  echo '{}' > "$(bdir ts8)/vet-triage.json"
  run set "$(bdir ts8)" closed --note "a" >/dev/null
  run set "$(bdir ts8)" reopened --note "b" >/dev/null
  echo '{}' > "$(bdir ts8)/vet-triage.json"
  run set "$(bdir ts8)" closed --note "c" >/dev/null
  local len; len=$(jq '.history | length' "$(bdir ts8)/bug.json")
  [ "$len" = "4" ] \
    && ok "s8: history len=4" \
    || ko "s8: history len=$len (expected 4)"
}

# s9: missing bug dir errors
s9() {
  local rc; rc=$(run get "$BUG_ROOT/does-not-exist")
  [ "$rc" != "0" ] && ok "s9: missing bug dir errors" || ko "s9: rc=$rc"
}

# s10: closing without vet-triage.json is blocked
s10() {
  mkbug ts10
  local rc; rc=$(run set "$(bdir ts10)" closed --note "no vet")
  [ "$rc" != "0" ] && grep -qi "vet" "$TMPROOT/stderr" \
    && ok "s10: close without vet-triage.json blocked" \
    || ko "s10: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# s11: closing with vet-triage.json succeeds
s11() {
  mkbug ts11
  echo '{"classification":"new","recommended_action":"route_to_feature_owner"}' \
    > "$(bdir ts11)/vet-triage.json"
  local rc; rc=$(run set "$(bdir ts11)" closed --note "triaged and fixed")
  local s; s=$(jq -r '.status' "$(bdir ts11)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && ok "s11: close with vet-triage.json succeeds" \
    || ko "s11: rc=$rc s=$s stderr=$(cat "$TMPROOT/stderr")"
}

# s12: --skip-vet-reason bypasses gate; history contains both skip-reason and original note
s12() {
  mkbug ts12
  local rc; rc=$(run set "$(bdir ts12)" closed \
    --note "fixed inline" --skip-vet-reason "closed by breeder in active scope")
  local s; s=$(jq -r '.status' "$(bdir ts12)/bug.json")
  local note; note=$(jq -r '.history[-1].note' "$(bdir ts12)/bug.json")
  [ "$rc" = "0" ] && [ "$s" = "closed" ] \
    && echo "$note" | grep -q "vet skipped" \
    && echo "$note" | grep -q "fixed inline" \
    && ok "s12: --skip-vet-reason bypasses gate, history has skip-reason and original note" \
    || ko "s12: rc=$rc s=$s note='$note'"
}

# s13: reopened->closed also requires vet gate
s13() {
  mkbug ts13
  echo '{}' > "$(bdir ts13)/vet-triage.json"
  run set "$(bdir ts13)" closed --note "first close" >/dev/null
  rm "$(bdir ts13)/vet-triage.json"
  run set "$(bdir ts13)" reopened --note "regression" >/dev/null
  local rc; rc=$(run set "$(bdir ts13)" closed --note "try close without vet")
  [ "$rc" != "0" ] && grep -qi "vet" "$TMPROOT/stderr" \
    && ok "s13: reopened->closed also requires vet gate" \
    || ko "s13: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

echo "running bug-status tests against $STATUS"
s1; s2; s3; s4; s5; s6; s7; s8; s9; s10; s11; s12; s13
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
