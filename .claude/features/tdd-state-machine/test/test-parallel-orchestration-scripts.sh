#!/bin/bash
# Tests for resolve-feature-scope.sh and dispatch-feature-tdd.sh.
# These scripts do not yet exist; t1 and t4 are expected to FAIL.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS_DIR="$FEATURE_DIR/scripts"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build a minimal RABBIT_ROOT fixture with registry.json + one feature.
make_rabbit_root() {
  local root="$1"
  mkdir -p "$root/.claude/features/tdd-state-machine/docs/spec"

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

  cat > "$root/.claude/features/tdd-state-machine/feature.json" <<'JSON'
{
  "name": "tdd-state-machine",
  "version": "1.0.0",
  "owner": "test",
  "tdd_state": "test-green",
  "summary": "fixture feature"
}
JSON

  echo "# Spec\nMinimal spec content." > "$root/.claude/features/tdd-state-machine/docs/spec/spec.md"
  echo "# Contract\nMinimal contract content." > "$root/.claude/features/tdd-state-machine/docs/spec/contract.md"
}

# ---------------------------------------------------------------------------
# t1: resolve-feature-scope.sh exists and is executable
# ---------------------------------------------------------------------------
t1() {
  [ -x "$SCRIPTS_DIR/resolve-feature-scope.sh" ] \
    && ok "t1: resolve-feature-scope.sh exists and is executable" \
    || ko "t1: resolve-feature-scope.sh not found or not executable at $SCRIPTS_DIR/resolve-feature-scope.sh"
}

# ---------------------------------------------------------------------------
# t2: resolve-feature-scope.sh exits 0 and emits non-empty stdout
# ---------------------------------------------------------------------------
t2() {
  local root="$TMPROOT/t2_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$SCRIPTS_DIR/resolve-feature-scope.sh" "add color to rabbit print" 2>/dev/null)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t2: resolve-feature-scope.sh exits 0 with non-empty stdout"
  else
    ko "t2: rc=$rc stdout_empty=$([ -z "$out" ] && echo yes || echo no)"
  fi
}

# ---------------------------------------------------------------------------
# t3: resolve-feature-scope.sh stdout contains the word "features"
# ---------------------------------------------------------------------------
t3() {
  local root="$TMPROOT/t3_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$SCRIPTS_DIR/resolve-feature-scope.sh" "add color to rabbit print" 2>/dev/null)
  echo "$out" | grep -qi "features" \
    && ok "t3: resolve-feature-scope.sh output contains 'features'" \
    || ko "t3: 'features' not found in output"
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
t1; t2; t3; t4; t5; t6; t7; t8
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
