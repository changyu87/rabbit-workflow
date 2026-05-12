#!/bin/bash
# Tests for dispatch-feature-tdd.sh --bug and --backlog optional parameters.
# Spec invariant 8: after test-green, orchestrator calls bug-status.sh or
# backlog-item-status.sh with the impl commit SHA.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS_DIR="$FEATURE_DIR/scripts"
DISPATCH_SH="$SCRIPTS_DIR/dispatch-feature-tdd.sh"
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

  printf '# Spec\nMinimal spec content.' > "$root/.claude/features/tdd-state-machine/docs/spec/spec.md"
  printf '# Contract\nMinimal contract content.' > "$root/.claude/features/tdd-state-machine/docs/spec/contract.md"
}

# ---------------------------------------------------------------------------
# t1: dispatch-feature-tdd.sh accepts --bug <bug-dir> without error
# ---------------------------------------------------------------------------
t1() {
  local root="$TMPROOT/t1_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --bug /some/bug/dir 2>&1)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t1: --bug accepted, exits 0 with non-empty stdout"
  else
    ko "t1: rc=$rc; expected 0. stderr/stdout: $out"
  fi
}

# ---------------------------------------------------------------------------
# t2: dispatch-feature-tdd.sh accepts --backlog <item-dir> without error
# ---------------------------------------------------------------------------
t2() {
  local root="$TMPROOT/t2_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --backlog /some/backlog/item 2>&1)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t2: --backlog accepted, exits 0 with non-empty stdout"
  else
    ko "t2: rc=$rc; expected 0. stderr/stdout: $out"
  fi
}

# ---------------------------------------------------------------------------
# t3: when --bug is given, emitted prompt contains bug-status.sh call
# ---------------------------------------------------------------------------
t3() {
  local root="$TMPROOT/t3_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --bug /bugs/my-bug 2>/dev/null)
  if echo "$out" | grep -q "bug-status.sh"; then
    ok "t3: prompt contains 'bug-status.sh'"
  else
    ko "t3: 'bug-status.sh' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t4: when --bug is given, emitted prompt contains the bug dir path
# ---------------------------------------------------------------------------
t4() {
  local root="$TMPROOT/t4_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --bug /bugs/my-bug 2>/dev/null)
  if echo "$out" | grep -q "/bugs/my-bug"; then
    ok "t4: prompt contains the bug dir path"
  else
    ko "t4: bug dir path '/bugs/my-bug' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t5: when --bug is given, emitted prompt contains 'closed'
# ---------------------------------------------------------------------------
t5() {
  local root="$TMPROOT/t5_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --bug /bugs/my-bug 2>/dev/null)
  if echo "$out" | grep -q "closed"; then
    ok "t5: prompt contains 'closed' (expected status for bug)"
  else
    ko "t5: 'closed' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t6: when --backlog is given, emitted prompt contains backlog-item-status.sh
# ---------------------------------------------------------------------------
t6() {
  local root="$TMPROOT/t6_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --backlog /backlogs/my-item 2>/dev/null)
  if echo "$out" | grep -q "backlog-item-status.sh"; then
    ok "t6: prompt contains 'backlog-item-status.sh'"
  else
    ko "t6: 'backlog-item-status.sh' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t7: when --backlog is given, emitted prompt contains the backlog item dir path
# ---------------------------------------------------------------------------
t7() {
  local root="$TMPROOT/t7_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --backlog /backlogs/my-item 2>/dev/null)
  if echo "$out" | grep -q "/backlogs/my-item"; then
    ok "t7: prompt contains the backlog item dir path"
  else
    ko "t7: backlog item dir path '/backlogs/my-item' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t8: when --backlog is given, emitted prompt contains 'implemented'
# ---------------------------------------------------------------------------
t8() {
  local root="$TMPROOT/t8_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --backlog /backlogs/my-item 2>/dev/null)
  if echo "$out" | grep -q "implemented"; then
    ok "t8: prompt contains 'implemented' (expected status for backlog)"
  else
    ko "t8: 'implemented' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t9: when neither --bug nor --backlog is given, prompt is still valid (no error)
# ---------------------------------------------------------------------------
t9() {
  local root="$TMPROOT/t9_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" 2>&1)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t9: baseline (no --bug/--backlog) still exits 0"
  else
    ko "t9: baseline broke: rc=$rc"
  fi
}

# ---------------------------------------------------------------------------
# t10: emitted prompt contains HANDOFF section when --bug given
# ---------------------------------------------------------------------------
t10() {
  local root="$TMPROOT/t10_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --bug /bugs/my-bug 2>/dev/null)
  if echo "$out" | grep -qi "HANDOFF"; then
    ok "t10: prompt contains HANDOFF section"
  else
    ko "t10: 'HANDOFF' not found in prompt"
  fi
}

echo "running dispatch-tdd-bug-backlog-params tests"
echo "  DISPATCH_SH=$DISPATCH_SH"
echo
t1; t2; t3; t4; t5; t6; t7; t8; t9; t10
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
