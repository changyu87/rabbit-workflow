#!/bin/bash
# End-to-end test of tdd-drift-check.sh.
# A feature claims a tdd_state; drift-check verifies state is consistent with
# what the actual test/run.sh does.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DRIFT="$FEATURE_DIR/scripts/tdd-drift-check.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build fixture with given state and test runner exit code.
fix() {
  local d="$1" n="$2" s="$3" rc="$4"
  mkdir -p "$d/test"
  cat > "$d/feature.json" <<JSON
{
  "name": "$n",
  "version": "0.1.0",
  "owner": { "primary": "test" },
  "status": "active",
  "tdd_state": "$s",
  "deprecation": { "criterion": "fixture" },
  "contract": { "reads": [], "writes": [], "invokes": [] },
  "created": "2026-05-08",
  "updated": "2026-05-08"
}
JSON
  echo > "$d/spec.md"; echo > "$d/contract.md"
  printf '#!/bin/bash\nexit %d\n' "$rc" > "$d/test/run.sh"
  chmod +x "$d/test/run.sh"
}

run() { "$DRIFT" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# d1: test-green claim + tests pass -> ok
d1() {
  local d="$TMPROOT/d1"; fix "$d" d1 test-green 0
  local rc; rc=$(run "$d")
  [ "$rc" = "0" ] && ok "d1: test-green + passing tests -> ok" \
    || ko "d1: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# d2: test-green claim + tests fail -> drift detected
d2() {
  local d="$TMPROOT/d2"; fix "$d" d2 test-green 1
  local rc; rc=$(run "$d")
  [ "$rc" != "0" ] && ok "d2: test-green + failing tests -> drift detected" \
    || ko "d2: rc=$rc"
}

# d3: test-red claim + tests fail -> ok (red is the expected state)
d3() {
  local d="$TMPROOT/d3"; fix "$d" d3 test-red 1
  local rc; rc=$(run "$d")
  [ "$rc" = "0" ] && ok "d3: test-red + failing tests -> ok" \
    || ko "d3: rc=$rc stderr=$(cat "$TMPROOT/stderr")"
}

# d4: test-red claim + tests pass -> drift (suspicious; tests should be red)
d4() {
  local d="$TMPROOT/d4"; fix "$d" d4 test-red 0
  local rc; rc=$(run "$d")
  [ "$rc" != "0" ] && ok "d4: test-red + passing tests -> drift" \
    || ko "d4: rc=$rc"
}

# d5: spec state -> not checked against tests (no claim about test outcome)
d5() {
  local d="$TMPROOT/d5"; fix "$d" d5 spec 1
  local rc; rc=$(run "$d")
  [ "$rc" = "0" ] && ok "d5: spec state -> ok regardless of tests" \
    || ko "d5: rc=$rc"
}

# d6: impl state is transitional - tests may pass or fail; both ok
d6() {
  local d1="$TMPROOT/d6a"; fix "$d1" d6a impl 0
  local d2="$TMPROOT/d6b"; fix "$d2" d6b impl 1
  local rc1; rc1=$(run "$d1")
  local rc2; rc2=$(run "$d2")
  [ "$rc1" = "0" ] && [ "$rc2" = "0" ] && ok "d6: impl state -> ok regardless of test outcome" \
    || ko "d6: rc1=$rc1 rc2=$rc2"
}

# d7: spec-update state -> not checked against tests (no claim about test outcome)
d7() {
  local d="$TMPROOT/d7"; fix "$d" d7 spec-update 1
  local rc; rc=$(run "$d")
  [ "$rc" = "0" ] && ok "d7: spec-update state -> ok regardless of tests" \
    || ko "d7: rc=$rc"
}

# d8: deprecated state -> not checked against tests
d8() {
  local d="$TMPROOT/d8"; fix "$d" d8 deprecated 1
  local rc; rc=$(run "$d")
  [ "$rc" = "0" ] && ok "d8: deprecated state -> ok regardless of tests" \
    || ko "d8: rc=$rc"
}

echo "running drift-check tests against $DRIFT"
d1; d2; d3; d4; d5; d6; d7; d8
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
