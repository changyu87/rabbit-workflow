#!/bin/bash
# End-to-end tests for file-bug.sh (new FEATURE-N naming interface).
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FILE_BUG="$FEATURE_DIR/scripts/file-bug.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

export BUG_ROOT="$TMPROOT/bugs"
mkdir -p "$BUG_ROOT"

run() { "$FILE_BUG" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# t1: first bug for a feature gets ID WORKLOG-1
t1() {
  local rc; rc=$(run --related-feature worklog --title "first worklog bug" --severity low --description "desc")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/WORKLOG-1/bug.json" ]; then
    ok "t1: first bug → WORKLOG-1"
  else
    ko "t1: rc=$rc stderr=$(cat "$TMPROOT/stderr") stdout=$(cat "$TMPROOT/stdout")"
  fi
}

# t2: second bug for same feature gets ID WORKLOG-2
t2() {
  local rc; rc=$(run --related-feature worklog --title "second" --severity low --description "d")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/WORKLOG-2/bug.json" ]; then
    ok "t2: second bug → WORKLOG-2"
  else
    ko "t2: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
  fi
}

# t3: hyphenated feature name uppercased and preserved
t3() {
  local rc; rc=$(run --related-feature install-distribute --title "x" --severity low --description "x")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/INSTALL-DISTRIBUTE-1/bug.json" ]; then
    ok "t3: install-distribute → INSTALL-DISTRIBUTE-1"
  else
    ko "t3: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
  fi
}

# t4: no --related-feature falls back to $BUG_PREFIX (default RBT)
t4() {
  local rc; rc=$(run --title "system bug" --severity medium --description "x")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/RBT-1/bug.json" ]; then
    ok "t4: no related-feature → RBT-1 (default prefix)"
  else
    ko "t4: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
  fi
}

# t5: $BUG_PREFIX env var overrides default prefix
t5() {
  local rc; rc=$(BUG_PREFIX=MYPROJ run --title "custom prefix" --severity low --description "x")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/MYPROJ-1/bug.json" ]; then
    ok "t5: BUG_PREFIX=MYPROJ → MYPROJ-1"
  else
    ko "t5: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
  fi
}

# t6: name field in bug.json matches directory name
t6() {
  run --related-feature worklog --title "x" --severity low --description "x" >/dev/null 2>&1 || true
  local name; name=$(jq -r '.name' "$BUG_ROOT/WORKLOG-1/bug.json" 2>/dev/null || echo "")
  [ "$name" = "WORKLOG-1" ] \
    && ok "t6: bug.json name field = WORKLOG-1" \
    || ko "t6: name='$name'"
}

# t7: related_feature recorded in bug.json
t7() {
  run --related-feature worklog --title "x" --severity low --description "x" >/dev/null 2>&1 || true
  local feat; feat=$(jq -r '.related_feature // ""' "$BUG_ROOT/WORKLOG-1/bug.json" 2>/dev/null || echo "")
  [ "$feat" = "worklog" ] \
    && ok "t7: related_feature recorded" \
    || ko "t7: got='$feat'"
}

# t8: status defaults to open
t8() {
  run --related-feature worklog --title "x" --severity low --description "x" >/dev/null 2>&1 || true
  local s; s=$(jq -r '.status' "$BUG_ROOT/WORKLOG-1/bug.json" 2>/dev/null || echo "")
  [ "$s" = "open" ] && ok "t8: default status is open" || ko "t8: got '$s'"
}

# t9: history seeded with one 'opened' entry
t9() {
  run --related-feature worklog --title "x" --severity low --description "x" >/dev/null 2>&1 || true
  local len; len=$(jq '.history | length' "$BUG_ROOT/WORKLOG-1/bug.json" 2>/dev/null || echo "0")
  local first; first=$(jq -r '.history[0].action' "$BUG_ROOT/WORKLOG-1/bug.json" 2>/dev/null || echo "")
  [ "$len" = "1" ] && [ "$first" = "opened" ] \
    && ok "t9: history has one 'opened' entry" \
    || ko "t9: len=$len first=$first"
}

# t10: invalid severity rejected
t10() {
  local rc; rc=$(run --related-feature worklog --title "x" --severity weird --description "x")
  [ "$rc" != "0" ] && grep -qi "severity" "$TMPROOT/stderr" \
    && ok "t10: invalid severity rejected" \
    || ko "t10: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# t11: missing --title rejected
t11() {
  local rc; rc=$(run --related-feature worklog --severity low --description "x")
  [ "$rc" != "0" ] && ok "t11: missing title rejected" || ko "t11: rc=$rc"
}

# t12: missing --description rejected
t12() {
  local rc; rc=$(run --related-feature worklog --title "x" --severity low)
  [ "$rc" != "0" ] && ok "t12: missing description rejected" || ko "t12: rc=$rc"
}

# t13: --name is no longer accepted (unknown arg)
t13() {
  local rc; rc=$(run --name "2026-05-08-old-style" --title "x" --severity low --description "x")
  [ "$rc" != "0" ] \
    && ok "t13: --name arg rejected (removed from interface)" \
    || ko "t13: rc=$rc (should have failed)"
}

# t14: output line contains the computed ID
t14() {
  run --related-feature worklog --title "filed" --severity low --description "x" >/dev/null 2>&1 || true
  run --related-feature worklog --title "second" --severity low --description "x" >"$TMPROOT/stdout" 2>&1 || true
  grep -q "WORKLOG-" "$TMPROOT/stdout" \
    && ok "t14: stdout contains computed ID (WORKLOG-N)" \
    || ko "t14: stdout='$(cat "$TMPROOT/stdout")'"
}

echo "running file-bug tests against $FILE_BUG"
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10; t11; t12; t13; t14
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
