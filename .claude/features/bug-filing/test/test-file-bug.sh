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

# t3: hyphenated feature name uppercased and preserved (use unknown feature so BUG_ROOT is respected)
t3() {
  local rc; rc=$(run --related-feature some-feature --title "x" --severity low --description "x")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/SOME-FEATURE-1/bug.json" ]; then
    ok "t3: some-feature → SOME-FEATURE-1"
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

# t15: --related-feature with invalid chars rejected
t15() {
  local rc; rc=$(run --related-feature "bad.name" --title "x" --severity low --description "x")
  [ "$rc" != "0" ] && grep -qi "related-feature" "$TMPROOT/stderr" \
    && ok "t15: invalid related-feature rejected" \
    || ko "t15: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# t-pf1: --related-feature policy routes bug into that feature's bugs_root
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
POLICY_BUGS_ROOT="$REPO_ROOT/.claude/features/policy/docs/bugs"
t_pf1() {
  local rc
  # Capture bug name from stdout so we can clean up
  "$FILE_BUG" --related-feature policy --title "pf1 test bug" --severity low \
    --description "per-feature routing test" >"$TMPROOT/pf1_out" 2>"$TMPROOT/pf1_err"
  rc=$?
  local bugname
  bugname=$(grep -oE 'POLICY-[0-9]+' "$TMPROOT/pf1_out" | head -1)
  if [ "$rc" = "0" ] && [ -n "$bugname" ] && [ -f "$POLICY_BUGS_ROOT/$bugname/bug.json" ] \
      && [ ! -f "$BUG_ROOT/$bugname/bug.json" ]; then
    ok "t-pf1: --related-feature policy → bug in $POLICY_BUGS_ROOT (not global)"
    # clean up
    rm -rf "$POLICY_BUGS_ROOT/$bugname"
  else
    ko "t-pf1: rc=$rc bugname=$bugname stderr=$(cat "$TMPROOT/pf1_err")"
    [ -n "$bugname" ] && rm -rf "$POLICY_BUGS_ROOT/$bugname"
  fi
}

# t-pf2: --related-feature nonexistent falls back to global BUG_ROOT with a warning
t_pf2() {
  local rc; rc=$(run --related-feature nonexistent --title "pf2 fallback" --severity low --description "fallback test")
  if [ "$rc" = "0" ] && [ -f "$BUG_ROOT/NONEXISTENT-1/bug.json" ] \
      && grep -qi "warning" "$TMPROOT/stderr"; then
    ok "t-pf2: nonexistent feature falls back to global BUG_ROOT with warning"
  else
    ko "t-pf2: rc=$rc stderr=$(cat "$TMPROOT/stderr") bug_exists=$([ -f "$BUG_ROOT/NONEXISTENT-1/bug.json" ] && echo yes || echo no)"
  fi
}

echo "running file-bug tests against $FILE_BUG"
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10; t11; t12; t13; t14; t15; t_pf1; t_pf2
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
