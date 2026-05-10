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

# pt1: transitioning to test-green calls rebuild-registry.sh if present.
pt1() {
  # Structure: TMPROOT/features/my-feature/feature.json
  # tdd-step.sh resolves rebuild-registry.sh relative to its own location:
  #   $(dirname BASH_SOURCE[0])/../../contract/scripts/rebuild-registry.sh
  # We can't easily override the script location, so we create a symlink
  # fixture that puts a stub rebuild-registry.sh at the expected relative path.
  #
  # Strategy: create a temp features dir; place feature at
  #   TMPROOT/features/my-feat/
  # Create a stub rebuild-registry.sh where tdd-step.sh would look:
  #   FEATURE_DIR/../contract/scripts/rebuild-registry.sh
  # (i.e., .claude/features/contract/scripts/) — but that's the real one.
  # Instead, we verify behavior by checking that the real rebuild-registry.sh
  # produces output when invoked by the hook (sentinel: registry.json written).

  local features_dir="$TMPROOT/pt1-features"
  local feat_dir="$features_dir/my-feat"
  fix "$feat_dir" "my-feat" "impl"

  # Create a stub contract/scripts/rebuild-registry.sh relative to tdd-step.sh.
  # tdd-step.sh location: FEATURE_DIR/scripts/tdd-step.sh
  # ../../contract/ from there => FEATURE_DIR/../../contract => one level above .claude/features
  # We can't do that in a temp dir easily.
  # Instead: create a completely isolated fixture that mirrors the real layout,
  # then symlink tdd-step.sh into it and set BASH_SOURCE via a wrapper.

  # Simpler: create the stub at the path the real tdd-step.sh resolves.
  # The real tdd-step.sh lives at .claude/features/tdd-state-machine/scripts/tdd-step.sh.
  # It resolves: .claude/features/tdd-state-machine/scripts/../../contract/scripts/rebuild-registry.sh
  #            = .claude/features/contract/scripts/rebuild-registry.sh
  # That's the real script. We create a minimal features dir and see if registry.json appears.

  local sentinel="$TMPROOT/pt1-sentinel"
  # Create a stub rebuild-registry.sh that writes sentinel file.
  # Place it where tdd-step.sh will look: tdd-step.sh dir + /../../contract/scripts/
  local stub_contract_dir
  stub_contract_dir="$(cd "$FEATURE_DIR/scripts/../../.." && pwd)/contract/scripts"
  # That's the real contract/scripts — we cannot overwrite it.
  # Use a wrapper approach: create a tiny wrapper tdd-step.sh that overrides REBUILD_SH.
  # Actually the cleanest test: just test that the hook code path is PRESENT in tdd-step.sh,
  # and separately test that the real rebuild-registry.sh works.
  # However the task requires an integration check via sentinel.

  # Wrapper approach: create a thin shell wrapper script that sets REBUILD_SH to our stub,
  # sources nothing, and calls the real tdd-step.sh with env override.
  # But tdd-step.sh uses a hardcoded local variable, not an env var.

  # Best practical approach without modifying tdd-step.sh:
  # Create a copy of tdd-step.sh in a temp mirrored layout, with a stub rebuild-registry.sh.

  local mirror_base="$TMPROOT/mirror"
  local mirror_tdd_scripts="$mirror_base/.claude/features/tdd-state-machine/scripts"
  local mirror_contract_scripts="$mirror_base/.claude/features/contract/scripts"
  local mirror_features="$mirror_base/.claude/features"
  local mirror_feat="$mirror_features/my-feat"

  mkdir -p "$mirror_tdd_scripts" "$mirror_contract_scripts" "$mirror_feat"

  # Copy real tdd-step.sh
  cp "$TDD_STEP" "$mirror_tdd_scripts/tdd-step.sh"
  chmod +x "$mirror_tdd_scripts/tdd-step.sh"

  # Create stub rebuild-registry.sh
  cat > "$mirror_contract_scripts/rebuild-registry.sh" <<'STUB'
#!/bin/bash
touch "$1/../pt1-sentinel"
STUB
  chmod +x "$mirror_contract_scripts/rebuild-registry.sh"

  # Place feature.json
  fix "$mirror_feat" "my-feat" "impl"

  # Run transition to test-green; set RABBIT_ROOT so the mirrored script finds stub scripts.
  RABBIT_ROOT="$mirror_base" "$mirror_tdd_scripts/tdd-step.sh" transition "$mirror_feat" test-green \
    >"$TMPROOT/stdout" 2>"$TMPROOT/stderr"
  local rc=$?

  # The stub writes sentinel at $1/../pt1-sentinel where $1 is FEATURES_DIR (mirror_features).
  # So sentinel = mirror_features/../pt1-sentinel = mirror_base/.claude/pt1-sentinel
  local expected_sentinel="$mirror_base/.claude/pt1-sentinel"

  [ "$rc" = "0" ] && [ -f "$expected_sentinel" ] \
    && ok "pt1: rebuild-registry.sh called on test-green transition (sentinel written)" \
    || ko "pt1: rc=$rc sentinel_exists=$([ -f "$expected_sentinel" ] && echo yes || echo no) stderr=$(cat "$TMPROOT/stderr")"
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

  RABBIT_ROOT="$mirror_base" "$mirror_tdd_scripts/tdd-step.sh" transition "$mirror_feat" test-red \
    >"$TMPROOT/stdout" 2>"$TMPROOT/stderr"
  local rc=$?

  local expected_sentinel="$mirror_base/.claude/pt2-sentinel"

  # Sentinel should NOT be written (hook only fires for test-green)
  [ "$rc" = "0" ] && [ ! -f "$expected_sentinel" ] \
    && ok "pt2: rebuild-registry.sh NOT called for non-test-green transition" \
    || ko "pt2: rc=$rc sentinel_exists=$([ -f "$expected_sentinel" ] && echo yes || echo no)"
}

# pt3: --force path also fires the hook on test-green.
pt3() {
  local mirror_base="$TMPROOT/mirror3"
  local mirror_tdd_scripts="$mirror_base/.claude/features/tdd-state-machine/scripts"
  local mirror_contract_scripts="$mirror_base/.claude/features/contract/scripts"
  local mirror_features="$mirror_base/.claude/features"
  local mirror_feat="$mirror_features/my-feat"

  mkdir -p "$mirror_tdd_scripts" "$mirror_contract_scripts" "$mirror_feat"
  cp "$TDD_STEP" "$mirror_tdd_scripts/tdd-step.sh"
  chmod +x "$mirror_tdd_scripts/tdd-step.sh"

  cat > "$mirror_contract_scripts/rebuild-registry.sh" <<'STUB'
#!/bin/bash
touch "$1/../pt3-sentinel"
STUB
  chmod +x "$mirror_contract_scripts/rebuild-registry.sh"

  # Start from spec and force to test-green (skip states)
  fix "$mirror_feat" "my-feat3" "spec"

  RABBIT_ROOT="$mirror_base" "$mirror_tdd_scripts/tdd-step.sh" transition "$mirror_feat" test-green --force \
    >"$TMPROOT/stdout" 2>"$TMPROOT/stderr"
  local rc=$?

  local expected_sentinel="$mirror_base/.claude/pt3-sentinel"

  [ "$rc" = "0" ] && [ -f "$expected_sentinel" ] \
    && ok "pt3: rebuild-registry.sh called on --force test-green transition (sentinel written)" \
    || ko "pt3: rc=$rc sentinel_exists=$([ -f "$expected_sentinel" ] && echo yes || echo no) stderr=$(cat "$TMPROOT/stderr")"
}

echo "running post-transition hook tests against $TDD_STEP"
pt1; pt2; pt3
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
