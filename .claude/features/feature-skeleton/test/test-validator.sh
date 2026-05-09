#!/bin/bash
# End-to-end test of validate-feature.sh.
# Each case builds a fixture in a temp dir, runs the validator, and asserts
# exit code + a substring in stderr.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATOR="$FEATURE_DIR/scripts/validate-feature.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0
FAIL=0

note() { echo "  $*"; }
ok()   { echo "  ok   $*"; PASS=$((PASS+1)); }
ko()   { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build a minimally-valid feature directory at $1 with name $2.
build_valid() {
  local dir="$1" name="$2"
  mkdir -p "$dir/test"
  cat > "$dir/feature.json" <<JSON
{
  "name": "$name",
  "version": "0.1.0",
  "owner": { "primary": "test-owner", "contact": "test@example.com" },
  "status": "active",
  "tdd_state": "test-green",
  "deprecation": { "criterion": "When fixture is dropped", "successor": null },
  "contract": { "reads": [], "writes": [], "invokes": [] },
  "created": "2026-05-08",
  "updated": "2026-05-08"
}
JSON
  echo "# spec" > "$dir/spec.md"
  echo "# contract" > "$dir/contract.md"
  cat > "$dir/test/run.sh" <<'SH'
#!/bin/bash
exit 0
SH
  chmod +x "$dir/test/run.sh"
}

# Run validator and return exit code; stderr captured to $TMPROOT/stderr.
run_validator() {
  local dir="$1"
  "$VALIDATOR" "$dir" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"
  echo $?
}

# t1: valid feature passes
t1() {
  local d="$TMPROOT/t1-valid" rc
  build_valid "$d" "t1-valid"
  rc=$(run_validator "$d")
  [ "$rc" = "0" ] && ok "t1: valid feature passes (rc=0)" || ko "t1: expected rc=0 got rc=$rc; stderr: $(cat "$TMPROOT/stderr")"
}

# t2: missing feature.json fails
t2() {
  local d="$TMPROOT/t2-no-json" rc
  build_valid "$d" "t2-no-json"
  rm "$d/feature.json"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "feature.json" "$TMPROOT/stderr" \
    && ok "t2: missing feature.json fails" \
    || ko "t2: expected non-zero with feature.json msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t3: invalid tdd_state fails
t3() {
  local d="$TMPROOT/t3-bad-tdd" rc
  build_valid "$d" "t3-bad-tdd"
  jq '.tdd_state = "bogus"' "$d/feature.json" > "$d/tmp.json" && mv "$d/tmp.json" "$d/feature.json"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "tdd_state" "$TMPROOT/stderr" \
    && ok "t3: invalid tdd_state fails" \
    || ko "t3: expected non-zero with tdd_state msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t4: name mismatch fails
t4() {
  local d="$TMPROOT/t4-name" rc
  build_valid "$d" "wrong-name"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "name" "$TMPROOT/stderr" \
    && ok "t4: name mismatch fails" \
    || ko "t4: expected non-zero with name msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t5: missing spec.md fails
t5() {
  local d="$TMPROOT/t5-no-spec" rc
  build_valid "$d" "t5-no-spec"
  rm "$d/spec.md"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "spec.md" "$TMPROOT/stderr" \
    && ok "t5: missing spec.md fails" \
    || ko "t5: expected non-zero with spec.md msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t6: missing contract.md fails
t6() {
  local d="$TMPROOT/t6-no-contract" rc
  build_valid "$d" "t6-no-contract"
  rm "$d/contract.md"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "contract.md" "$TMPROOT/stderr" \
    && ok "t6: missing contract.md fails" \
    || ko "t6: expected non-zero with contract.md msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t7: missing test/run.sh fails
t7() {
  local d="$TMPROOT/t7-no-run" rc
  build_valid "$d" "t7-no-run"
  rm "$d/test/run.sh"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "run.sh" "$TMPROOT/stderr" \
    && ok "t7: missing test/run.sh fails" \
    || ko "t7: expected non-zero with run.sh msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t8: test/run.sh not executable fails
t8() {
  local d="$TMPROOT/t8-not-exec" rc
  build_valid "$d" "t8-not-exec"
  chmod -x "$d/test/run.sh"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "executable" "$TMPROOT/stderr" \
    && ok "t8: non-executable run.sh fails" \
    || ko "t8: expected non-zero with executable msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t9: missing deprecation.criterion fails
t9() {
  local d="$TMPROOT/t9-no-deprec" rc
  build_valid "$d" "t9-no-deprec"
  jq 'del(.deprecation.criterion)' "$d/feature.json" > "$d/tmp.json" && mv "$d/tmp.json" "$d/feature.json"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "deprecation" "$TMPROOT/stderr" \
    && ok "t9: missing deprecation.criterion fails" \
    || ko "t9: expected non-zero with deprecation msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t10: missing owner.primary fails
t10() {
  local d="$TMPROOT/t10-no-owner" rc
  build_valid "$d" "t10-no-owner"
  jq 'del(.owner.primary)' "$d/feature.json" > "$d/tmp.json" && mv "$d/tmp.json" "$d/feature.json"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "owner" "$TMPROOT/stderr" \
    && ok "t10: missing owner.primary fails" \
    || ko "t10: expected non-zero with owner msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t11: invalid version (not semver) fails
t11() {
  local d="$TMPROOT/t11-bad-ver" rc
  build_valid "$d" "t11-bad-ver"
  jq '.version = "v1"' "$d/feature.json" > "$d/tmp.json" && mv "$d/tmp.json" "$d/feature.json"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "version" "$TMPROOT/stderr" \
    && ok "t11: invalid version fails" \
    || ko "t11: expected non-zero with version msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t12: invalid status fails
t12() {
  local d="$TMPROOT/t12-bad-status" rc
  build_valid "$d" "t12-bad-status"
  jq '.status = "weird"' "$d/feature.json" > "$d/tmp.json" && mv "$d/tmp.json" "$d/feature.json"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && grep -q "status" "$TMPROOT/stderr" \
    && ok "t12: invalid status fails" \
    || ko "t12: expected non-zero with status msg; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t13: malformed JSON fails
t13() {
  local d="$TMPROOT/t13-bad-json" rc
  build_valid "$d" "t13-bad-json"
  echo "not json {" > "$d/feature.json"
  rc=$(run_validator "$d")
  [ "$rc" != "0" ] && ok "t13: malformed JSON fails" \
    || ko "t13: expected non-zero; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

# t14: validator self-test - running on its own feature dir passes
t14() {
  local rc
  rc=$(run_validator "$FEATURE_DIR")
  [ "$rc" = "0" ] && ok "t14: feature-skeleton validates itself" \
    || ko "t14: feature-skeleton failed self-validation; rc=$rc stderr: $(cat "$TMPROOT/stderr")"
}

echo "running validator tests against $VALIDATOR"
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10; t11; t12; t13; t14

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
