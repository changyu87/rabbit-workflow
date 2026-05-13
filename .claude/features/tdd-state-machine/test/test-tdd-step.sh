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
  [ "$rc" = "0" ] && [ "$(cat "$TMPROOT/stdout")" = "spec-update" ] \
    && ok "t2: next from spec is spec-update" \
    || ko "t2: rc=$rc out='$(cat "$TMPROOT/stdout")'"
}

# t3: transition to next-allowed succeeds and writes file
t3() {
  local d="$TMPROOT/t3"; fix "$d" t3 spec
  local rc; rc=$(run transition "$d" spec-update)
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" = "0" ] && [ "$newstate" = "spec-update" ] \
    && ok "t3: spec -> spec-update succeeds" \
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
  run transition "$d" spec-update >/dev/null
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
  run transition "$d" spec-update >/dev/null || ok=0
  [ "$ok" = "1" ] && run transition "$d" test-red --spec-no-change-reason "t9 full-path fixture" >/dev/null || ok=0
  for next in impl test-green review merged deprecated; do
    [ "$ok" = "1" ] && run transition "$d" "$next" >/dev/null || { ok=0; break; }
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

# t_su1: spec-update is a valid state (--force into spec-update must succeed)
t_su1() {
  local d="$TMPROOT/tsu1"; fix "$d" tsu1 spec
  local rc; rc=$(run transition "$d" spec-update --force)
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" = "0" ] && [ "$newstate" = "spec-update" ] \
    && ok "tsu1: spec-update is a valid state (--force accepted)" \
    || ko "tsu1: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/stderr")"
}

# t_su2: spec → spec-update is the forward transition from spec
t_su2() {
  local d="$TMPROOT/tsu2"; fix "$d" tsu2 spec
  local rc; rc=$(run transition "$d" spec-update)
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" = "0" ] && [ "$newstate" = "spec-update" ] \
    && ok "tsu2: spec -> spec-update forward transition succeeds" \
    || ko "tsu2: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/stderr")"
}

# t_su3: spec-update → test-red allowed when --spec-no-change-reason provided
t_su3() {
  local d="$TMPROOT/tsu3"; fix "$d" tsu3 spec-update
  local rc; rc=$(run transition "$d" test-red --spec-no-change-reason "bug fix; spec already correct")
  local newstate; newstate=$(jq -r '.tdd_state' "$d/feature.json")
  [ "$rc" = "0" ] && [ "$newstate" = "test-red" ] \
    && ok "tsu3: spec-update -> test-red with --spec-no-change-reason succeeds" \
    || ko "tsu3: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/stderr")"
}

# t_su4: spec-update → test-red blocked when spec unmodified and no reason given
t_su4() {
  local d="$TMPROOT/tsu4_repo"
  git init "$d" >/dev/null 2>&1
  git -C "$d" config user.email "test@test.com"
  git -C "$d" config user.name "Test"
  local feat="$d/feat"; fix "$feat" tsu4 spec-update
  mkdir -p "$feat/docs/spec"
  echo "spec content" > "$feat/docs/spec/spec.md"
  git -C "$d" add -A >/dev/null 2>&1
  git -C "$d" commit -m "init" >/dev/null 2>&1
  # spec.md NOT modified after commit → gate must block
  # Cannot use run() helper — must inject RABBIT_ROOT to point at the temp git repo.
  local rc
  RABBIT_ROOT="$d" "$TDD_STEP" transition "$feat" test-red >"$TMPROOT/stdout_tsu4" 2>"$TMPROOT/err_tsu4"
  rc=$?
  local newstate; newstate=$(jq -r '.tdd_state' "$feat/feature.json")
  # Currently passes because spec-update is not yet a valid state (rc!=0 for wrong reason).
  # After Task 2 implementation, this tests the actual spec-diff enforcement gate.
  [ "$rc" != "0" ] && [ "$newstate" = "spec-update" ] \
    && ok "tsu4: spec-update -> test-red blocked when spec unmodified and no reason" \
    || ko "tsu4: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/err_tsu4")"
}

# t_su5: spec-update → test-red allowed when spec.md modified (git diff detects change)
t_su5() {
  local d="$TMPROOT/tsu5_repo"
  git init "$d" >/dev/null 2>&1
  git -C "$d" config user.email "test@test.com"
  git -C "$d" config user.name "Test"
  local feat="$d/feat"; fix "$feat" tsu5 spec-update
  mkdir -p "$feat/docs/spec"
  echo "original spec" > "$feat/docs/spec/spec.md"
  git -C "$d" add -A >/dev/null 2>&1
  git -C "$d" commit -m "init" >/dev/null 2>&1
  # Modify spec.md → git diff will show changes → gate must allow
  echo "updated spec" >> "$feat/docs/spec/spec.md"
  # Cannot use run() helper — must inject RABBIT_ROOT to point at the temp git repo.
  local rc
  RABBIT_ROOT="$d" "$TDD_STEP" transition "$feat" test-red >"$TMPROOT/stdout_tsu5" 2>"$TMPROOT/err_tsu5"
  rc=$?
  local newstate; newstate=$(jq -r '.tdd_state' "$feat/feature.json")
  [ "$rc" = "0" ] && [ "$newstate" = "test-red" ] \
    && ok "tsu5: spec-update -> test-red allowed when spec.md modified in git" \
    || ko "tsu5: rc=$rc newstate=$newstate stderr=$(cat "$TMPROOT/err_tsu5")"
}

# t_su6: next from spec-update is test-red
t_su6() {
  local d="$TMPROOT/tsu6"; fix "$d" tsu6 spec-update
  local rc; rc=$(run next "$d")
  [ "$rc" = "0" ] && [ "$(cat "$TMPROOT/stdout")" = "test-red" ] \
    && ok "tsu6: next from spec-update is test-red" \
    || ko "tsu6: rc=$rc out='$(cat "$TMPROOT/stdout")'"
}

# t_rbt1: tdd-step.sh transition stdout contains literal "[rabbit]"
t_rbt1() {
  local d="$TMPROOT/t_rbt1"; fix "$d" t_rbt1 spec
  run transition "$d" spec-update >/dev/null
  local out; out="$(cat "$TMPROOT/stdout")"
  echo "$out" | grep -q '\[rabbit\]' \
    && ok "t_rbt1: transition stdout contains [rabbit]" \
    || ko "t_rbt1: [rabbit] not found in stdout: '$out'"
}

# t_rbt2: tdd-step.sh transition stdout contains ANSI green code
t_rbt2() {
  local d="$TMPROOT/t_rbt2"; fix "$d" t_rbt2 spec
  run transition "$d" spec-update >/dev/null
  local out; out="$(cat "$TMPROOT/stdout")"
  # Check for ESC character followed by [32m
  printf '%s' "$out" | python3 -c "import sys; s=sys.stdin.read(); exit(0 if '\x1b[32m' in s else 1)" \
    && ok "t_rbt2: transition stdout contains ANSI green (\x1b[32m)" \
    || ko "t_rbt2: ANSI green not found in stdout"
}

# t_rbt3: tdd-step.sh transition --force stderr contains ANSI red code
t_rbt3() {
  local d="$TMPROOT/t_rbt3"; fix "$d" t_rbt3 impl
  run transition "$d" test-red --force >/dev/null
  local err; err="$(cat "$TMPROOT/stderr")"
  printf '%s' "$err" | python3 -c "import sys; s=sys.stdin.read(); exit(0 if '\x1b[31m' in s else 1)" \
    && ok "t_rbt3: forced transition stderr contains ANSI red (\x1b[31m)" \
    || ko "t_rbt3: ANSI red not found in stderr: '$(printf '%s' "$err" | cat -v)'"
}

# t_ref1: _run_enforcement_checks is defined as a function in tdd-step.sh
t_ref1() {
  grep -q "^_run_enforcement_checks()" "$TDD_STEP" \
    && ok "t_ref1: _run_enforcement_checks function is defined in tdd-step.sh" \
    || ko "t_ref1: _run_enforcement_checks function NOT found in tdd-step.sh"
}

# t_ref2: enforcement check block appears only once (no copy-paste duplication)
# Count bash invocations of the non-interactive check — should appear exactly once
# (in the function body), not duplicated at each former call site.
t_ref2() {
  local count
  count=$(grep -c 'bash.*check-tests-non-interactive.sh' "$TDD_STEP" 2>/dev/null || echo 0)
  [ "$count" -eq 1 ] \
    && ok "t_ref2: enforcement check block appears exactly once (count=$count)" \
    || ko "t_ref2: enforcement check block appears $count times (expected 1 — deduplication required)"
}

echo "running tdd-step tests against $TDD_STEP"
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10; t11
t_su1; t_su2; t_su3; t_su4; t_su5; t_su6
t_rbt1; t_rbt2; t_rbt3
t_ref1; t_ref2
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
