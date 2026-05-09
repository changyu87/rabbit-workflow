#!/bin/bash
# End-to-end test of tdd-step.sh: show, next, transitions, transition, --force.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TDD_STEP="$FEATURE_DIR/scripts/tdd-step.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok()   { echo "  ok   $*"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build a fixture feature dir at $1, name $2, tdd_state $3.
fix() {
  local d="$1" n="$2" s="$3"
  mkdir -p "$d/test"
  cat > "$d/feature.json" <<JSON
{
  "name": "$n",
  "version": "0.1.0",
  "owner": { "primary": "test", "contact": "" },
  "status": "active",
  "tdd_state": "$s",
  "deprecation": { "criterion": "fixture", "successor": null },
  "contract": { "reads": [], "writes": [], "invokes": [] },
  "created": "2026-05-08",
  "updated": "2026-05-08"
}
JSON
  echo "spec" > "$d/spec.md"
  echo "contract" > "$d/contract.md"
  printf '#!/bin/bash\nexit 0\n' > "$d/test/run.sh"
  chmod +x "$d/test/run.sh"
}

run() { "$TDD_STEP" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# t1: show returns current state
t1() {
  local d="$TMPROOT/t1"; fix "$d" t1 spec
  local rc; rc=$(run show "$d")
  [ "$rc" = "0" ] && [ "$(cat "$TMPROOT/stdout")" = "spec" ] \
    && ok "t1: show returns spec" \
    || ko "t1: rc=$rc out='$(cat "$TMPROOT/stdout")'"
}

# t2: next returns expected next state
t2() {
  local d="$TMPROOT/t2"; fix "$d" t2 spec
  local rc; rc=$(run next "$d")
  [ "$rc" = "0" ] && [ "$(cat "$TMPROOT/stdout")" = "test-red" ] \
    && ok "t2: next from spec is test-red" \
    || ko "t2: rc=$rc out='$(cat "$TMPROOT/stdout")'"
}

# t3: transition to next-allowed succeeds and writes file
t3() {
  local d="$TMPROOT/t3"; fix "$d" t3 spec
  local rc; rc=$(run transition "$d" test-red)
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" = "0" ] && [ "$newstate" = "test-red" ] \
    && ok "t3: spec -> test-red succeeds" \
    || ko "t3: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/stderr")"
}

# t4: skip transition denied (spec -> test-green)
t4() {
  local d="$TMPROOT/t4"; fix "$d" t4 spec
  local rc; rc=$(run transition "$d" test-green)
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" != "0" ] && [ "$newstate" = "spec" ] \
    && ok "t4: spec -> test-green denied (skip)" \
    || ko "t4: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/stderr")"
}

# t5: backward transition denied without --force (impl -> test-red)
t5() {
  local d="$TMPROOT/t5"; fix "$d" t5 impl
  local rc; rc=$(run transition "$d" test-red)
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" != "0" ] && [ "$newstate" = "impl" ] \
    && ok "t5: impl -> test-red denied without --force" \
    || ko "t5: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/stderr")"
}

# t6: backward transition with --force succeeds
t6() {
  local d="$TMPROOT/t6"; fix "$d" t6 impl
  local rc; rc=$(run transition "$d" test-red --force)
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" = "0" ] && [ "$newstate" = "test-red" ] \
    && ok "t6: impl -> test-red allowed with --force" \
    || ko "t6: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/stderr")"
}

# t7: transition updates the 'updated' field
t7() {
  local d="$TMPROOT/t7"; fix "$d" t7 spec
  jq '.updated = "1999-01-01"' "$d/feature.json" > "$d/tmp" && mv "$d/tmp" "$d/feature.json"
  run transition "$d" test-red >/dev/null
  local upd; upd=$(jq -r '.updated' "$d/feature.json")
  [ "$upd" != "1999-01-01" ] && echo "$upd" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' \
    && ok "t7: 'updated' field refreshed to $upd" \
    || ko "t7: updated=$upd"
}

# t8: terminal state - deprecated cannot transition
t8() {
  local d="$TMPROOT/t8"; fix "$d" t8 deprecated
  local rc; rc=$(run transition "$d" merged --force)
  [ "$rc" != "0" ] \
    && ok "t8: deprecated is terminal (no exit even with --force)" \
    || ko "t8: rc=$rc - deprecated should not be exitable"
}

# t9: full forward path works end-to-end
t9() {
  local d="$TMPROOT/t9"; fix "$d" t9 spec
  local ok=1
  for next in test-red impl test-green review merged deprecated; do
    run transition "$d" "$next" >/dev/null || { ok=0; break; }
  done
  local final; final=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$ok" = "1" ] && [ "$final" = "deprecated" ] \
    && ok "t9: full forward path spec -> deprecated" \
    || ko "t9: ok=$ok final=$final"
}

# t10: invalid target state denied
t10() {
  local d="$TMPROOT/t10"; fix "$d" t10 spec
  local rc; rc=$(run transition "$d" bogus)
  [ "$rc" != "0" ] \
    && ok "t10: invalid target state denied" \
    || ko "t10: rc=$rc"
}

# t11: transitions sub-command lists allowed next states (forward without --force)
t11() {
  local d="$TMPROOT/t11"; fix "$d" t11 review
  local rc; rc=$(run transitions "$d")
  local out; out=$(cat "$TMPROOT/stdout")
  [ "$rc" = "0" ] && echo "$out" | grep -q "merged" \
    && ok "t11: transitions from review includes merged" \
    || ko "t11: rc=$rc out='$out'"
}

echo "running tdd-step tests against $TDD_STEP"
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10; t11
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
