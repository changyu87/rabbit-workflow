#!/bin/bash
# test-post-transition.sh — verify post-transition hooks fire on test-green.
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
  mkdir -p "$d"
  cat > "$d/feature.json" <<JSON
{
  "name": "$n",
  "version": "0.1.0",
  "owner": "test",
  "tdd_state": "$s"
}
JSON
}

run() { "$TDD_STEP" "$@" 2>"$TMPROOT/stderr" >"$TMPROOT/stdout"; echo $?; }

# pt1: rebuild-registry.sh hook is NOT present in tdd-step.sh (deleted in Task 5).
pt1() {
  grep -q "rebuild-registry.sh" "$TDD_STEP" \
    && ko "pt1: rebuild-registry.sh reference still present in tdd-step.sh" \
    || ok "pt1: rebuild-registry.sh hook correctly absent from tdd-step.sh"
}

# pt2: test-green hook NOT called for other transitions (e.g., spec -> test-red).
pt2() {
  local mirror_base="$TMPROOT/mirror2"
  local mirror_tdd_scripts="$mirror_base/.claude/features/tdd-state-machine/scripts"
  local mirror_contract_scripts="$mirror_base/.claude/features/contract/scripts"
  local mirror_features="$mirror_base/.claude/features"
  local mirror_feat="$mirror_features/my-feat"

  mkdir -p "$mirror_tdd_scripts" "$mirror_contract_scripts" "$mirror_feat"
  cp "$TDD_STEP" "$mirror_tdd_scripts/tdd-step.sh"
  chmod +x "$mirror_tdd_scripts/tdd-step.sh"

  cat > "$mirror_contract_scripts/rebuild-registry.sh" <<'STUB'
#!/bin/bash
touch "$1/../pt2-sentinel"
STUB
  chmod +x "$mirror_contract_scripts/rebuild-registry.sh"

  fix "$mirror_feat" "my-feat2" "spec"

  RABBIT_ROOT="$mirror_base" "$mirror_tdd_scripts/tdd-step.sh" transition "$mirror_feat" spec-update \
    >"$TMPROOT/stdout" 2>"$TMPROOT/stderr"
  local rc=$?

  local expected_sentinel="$mirror_base/.claude/pt2-sentinel"

  # Sentinel should NOT be written (hook only fires for test-green)
  [ "$rc" = "0" ] && [ ! -f "$expected_sentinel" ] \
    && ok "pt2: rebuild-registry.sh NOT called for non-test-green transition" \
    || ko "pt2: rc=$rc sentinel_exists=$([ -f "$expected_sentinel" ] && echo yes || echo no)"
}

# pt3: --force path to test-green succeeds and does not call rebuild-registry.sh.
pt3() {
  local mirror_base="$TMPROOT/mirror3"
  local mirror_tdd_scripts="$mirror_base/.claude/features/tdd-state-machine/scripts"
  local mirror_contract_scripts="$mirror_base/.claude/features/contract/scripts"
  local mirror_features="$mirror_base/.claude/features"
  local mirror_feat="$mirror_features/my-feat"

  mkdir -p "$mirror_tdd_scripts" "$mirror_contract_scripts" "$mirror_feat"
  cp "$TDD_STEP" "$mirror_tdd_scripts/tdd-step.sh"
  chmod +x "$mirror_tdd_scripts/tdd-step.sh"

  # Start from spec and force to test-green (skip states)
  fix "$mirror_feat" "my-feat3" "spec"

  RABBIT_ROOT="$mirror_base" "$mirror_tdd_scripts/tdd-step.sh" transition "$mirror_feat" test-green --force \
    >"$TMPROOT/stdout" 2>"$TMPROOT/stderr"
  local rc=$?

  # rebuild-registry.sh hook is gone; no sentinel should be written anywhere
  local unexpected_sentinel="$mirror_base/.claude/pt3-sentinel"

  [ "$rc" = "0" ] && [ ! -f "$unexpected_sentinel" ] \
    && ok "pt3: --force test-green succeeds; rebuild-registry.sh hook absent (no sentinel)" \
    || ko "pt3: rc=$rc sentinel_exists=$([ -f "$unexpected_sentinel" ] && echo yes || echo no) stderr=$(cat "$TMPROOT/stderr")"
}

echo "running post-transition hook tests against $TDD_STEP"
pt1; pt2; pt3
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
