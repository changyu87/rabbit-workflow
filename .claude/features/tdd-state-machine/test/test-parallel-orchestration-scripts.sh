#!/bin/bash
# Tests for dispatch-feature-tdd.sh.
# resolve-feature-scope.sh was deleted in Task 5 (replaced by rabbit-feature-scope feature).
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS_DIR="$FEATURE_DIR/scripts"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

FIND_FEATURE_SH="$(cd "$SCRIPT_DIR/../.." && pwd)/contract/scripts/find-feature.sh"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build a minimal RABBIT_ROOT fixture with registry.json, find-feature.sh, and one feature.
make_rabbit_root() {
  local root="$1"
  mkdir -p "$root/.claude/features/tdd-state-machine/docs/spec"
  mkdir -p "$root/.claude/features/contract/scripts"

  # registry.json — still needed by resolve-feature-scope.sh (not migrated; deleted in Task 5).
  cat > "$root/.claude/features/registry.json" <<'JSON'
{
  "schema_version": "1.0.0",
  "owner": "test",
  "features": {
    "tdd-state-machine": {
      "name": "tdd-state-machine",
      "version": "1.0.0",
      "owner": "test",
      "tdd_state": "test-green",
      "summary": "fixture feature",
      "path": ".claude/features/tdd-state-machine"
    }
  }
}
JSON

  # feature.json — needed by find-feature.sh (used by dispatch-feature-tdd.sh).
  cat > "$root/.claude/features/tdd-state-machine/feature.json" <<'JSON'
{
  "name": "tdd-state-machine",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "fixture feature"
}
JSON

  # Copy find-feature.sh so dispatch-feature-tdd.sh can locate the feature.
  cp "$FIND_FEATURE_SH" "$root/.claude/features/contract/scripts/find-feature.sh"
  cp "$(dirname "$FIND_FEATURE_SH")/find-feature.py" "$root/.claude/features/contract/scripts/find-feature.py"

  echo "# Spec\nMinimal spec content." > "$root/.claude/features/tdd-state-machine/docs/spec/spec.md"
  echo "# Contract\nMinimal contract content." > "$root/.claude/features/tdd-state-machine/docs/spec/contract.md"
}

# ---------------------------------------------------------------------------
# t1: resolve-feature-scope.sh does NOT exist (deleted in Task 5)
# ---------------------------------------------------------------------------
t1() {
  [ ! -f "$SCRIPTS_DIR/resolve-feature-scope.sh" ] \
    && ok "t1: resolve-feature-scope.sh correctly absent (deleted in Task 5)" \
    || ko "t1: resolve-feature-scope.sh still exists but should have been deleted"
}

# ---------------------------------------------------------------------------
# t4: dispatch-feature-tdd.sh exists and is executable
# ---------------------------------------------------------------------------
t4() {
  [ -x "$SCRIPTS_DIR/dispatch-feature-tdd.sh" ] \
    && ok "t4: dispatch-feature-tdd.sh exists and is executable" \
    || ko "t4: dispatch-feature-tdd.sh not found or not executable at $SCRIPTS_DIR/dispatch-feature-tdd.sh"
}

# ---------------------------------------------------------------------------
# t5: dispatch-feature-tdd.sh exits 0 and emits non-empty stdout
# ---------------------------------------------------------------------------
t5() {
  local root="$TMPROOT/t5_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$SCRIPTS_DIR/dispatch-feature-tdd.sh" tdd-state-machine "add color" 2>/dev/null)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t5: dispatch-feature-tdd.sh exits 0 with non-empty stdout"
  else
    ko "t5: rc=$rc stdout_empty=$([ -z "$out" ] && echo yes || echo no)"
  fi
}

# ---------------------------------------------------------------------------
# t6: dispatch-feature-tdd.sh stdout contains "SCOPE"
# ---------------------------------------------------------------------------
t6() {
  local root="$TMPROOT/t6_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$SCRIPTS_DIR/dispatch-feature-tdd.sh" tdd-state-machine "add color" 2>/dev/null)
  echo "$out" | grep -q "SCOPE" \
    && ok "t6: dispatch-feature-tdd.sh output contains 'SCOPE'" \
    || ko "t6: 'SCOPE' not found in output"
}

# ---------------------------------------------------------------------------
# t7: dispatch-feature-tdd.sh stdout contains "spec-update"
# ---------------------------------------------------------------------------
t7() {
  local root="$TMPROOT/t7_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$SCRIPTS_DIR/dispatch-feature-tdd.sh" tdd-state-machine "add color" 2>/dev/null)
  echo "$out" | grep -q "spec-update" \
    && ok "t7: dispatch-feature-tdd.sh output contains 'spec-update'" \
    || ko "t7: 'spec-update' not found in output"
}

# ---------------------------------------------------------------------------
# t8: dispatch-feature-tdd.sh stdout contains ".rabbit-scope-active-"
# ---------------------------------------------------------------------------
t8() {
  local root="$TMPROOT/t8_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$SCRIPTS_DIR/dispatch-feature-tdd.sh" tdd-state-machine "add color" 2>/dev/null)
  echo "$out" | grep -q "\.rabbit-scope-active-" \
    && ok "t8: dispatch-feature-tdd.sh output contains '.rabbit-scope-active-'" \
    || ko "t8: '.rabbit-scope-active-' not found in output"
}

echo "running parallel-orchestration-scripts tests"
echo "  SCRIPTS_DIR=$SCRIPTS_DIR"
echo
t1; t4; t5; t6; t7; t8
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
