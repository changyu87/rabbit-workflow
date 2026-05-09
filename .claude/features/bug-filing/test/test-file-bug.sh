#!/bin/bash
# End-to-end tests for file-bug.sh.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FILE_BUG="$FEATURE_DIR/scripts/file-bug.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# All file-bug.sh invocations are scoped to a fake bugs root via env var.
export BUG_ROOT="$TMPROOT/bugs"
mkdir -p "$BUG_ROOT"

run() { "$FILE_BUG" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# t1: file a new bug succeeds and creates bug.json
t1() {
  local rc; rc=$(run --name "2026-05-08-test-one" --title "test bug one" --severity low --description "desc")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/2026-05-08-test-one/bug.json" ]; then
    ok "t1: file bug creates dir and bug.json"
  else
    ko "t1: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
  fi
}

# t2: duplicate name rejected
t2() {
  run --name "2026-05-08-dup" --title "first" --severity low --description "a" >/dev/null
  local rc; rc=$(run --name "2026-05-08-dup" --title "second" --severity low --description "b")
  [ "$rc" != "0" ] && grep -qi "exist" "$TMPROOT/stderr" \
    && ok "t2: duplicate name rejected" \
    || ko "t2: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# t3: invalid name (uppercase) rejected
t3() {
  local rc; rc=$(run --name "2026-05-08-BadName" --title "x" --severity low --description "x")
  [ "$rc" != "0" ] && grep -qi "name" "$TMPROOT/stderr" \
    && ok "t3: invalid name (uppercase) rejected" \
    || ko "t3: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# t4: invalid name (no date prefix) rejected
t4() {
  local rc; rc=$(run --name "broken-thing" --title "x" --severity low --description "x")
  [ "$rc" != "0" ] && grep -qi "name" "$TMPROOT/stderr" \
    && ok "t4: invalid name (no date prefix) rejected" \
    || ko "t4: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# t5: missing required field (title) rejected
t5() {
  local rc; rc=$(run --name "2026-05-08-no-title" --severity low --description "x")
  [ "$rc" != "0" ] && ok "t5: missing title rejected" \
    || ko "t5: rc=$rc"
}

# t6: invalid severity rejected
t6() {
  local rc; rc=$(run --name "2026-05-08-bad-sev" --title "x" --severity weird --description "x")
  [ "$rc" != "0" ] && grep -qi "severity" "$TMPROOT/stderr" \
    && ok "t6: invalid severity rejected" \
    || ko "t6: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# t7: optional --related-feature recorded
t7() {
  run --name "2026-05-08-with-feat" --title "x" --severity low --description "x" --related-feature "feature-skeleton" >/dev/null
  local got; got=$(jq -r '.related_feature // ""' "$BUG_ROOT/2026-05-08-with-feat/bug.json")
  [ "$got" = "feature-skeleton" ] \
    && ok "t7: related_feature recorded" \
    || ko "t7: got='$got'"
}

# t8: status defaults to open
t8() {
  run --name "2026-05-08-status-default" --title "x" --severity low --description "x" >/dev/null
  local s; s=$(jq -r '.status' "$BUG_ROOT/2026-05-08-status-default/bug.json")
  [ "$s" = "open" ] && ok "t8: default status is open" || ko "t8: got '$s'"
}

# t9: history seeded with one 'opened' entry
t9() {
  run --name "2026-05-08-history-seed" --title "x" --severity low --description "x" >/dev/null
  local len; len=$(jq '.history | length' "$BUG_ROOT/2026-05-08-history-seed/bug.json")
  local first; first=$(jq -r '.history[0].action' "$BUG_ROOT/2026-05-08-history-seed/bug.json")
  [ "$len" = "1" ] && [ "$first" = "opened" ] \
    && ok "t9: history has one 'opened' entry" \
    || ko "t9: len=$len first=$first"
}

# t10: name length limit enforced (>60 chars rejected)
t10() {
  local longname="2026-05-08-$(printf 'a%.0s' {1..70})"
  local rc; rc=$(run --name "$longname" --title "x" --severity low --description "x")
  [ "$rc" != "0" ] && ok "t10: overly long name rejected" || ko "t10: rc=$rc"
}

echo "running file-bug tests against $FILE_BUG"
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
