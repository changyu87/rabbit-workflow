#!/bin/bash
# Tests for dispatch-feature-tdd.sh --linked-item / --item-type parameters.
# Updated in v2.0.0: --bug and --backlog are removed; the unified --linked-item
# interface replaces them. The TDD subagent writes tdd-report.json; callers
# handle status updates after reading the report.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS_DIR="$FEATURE_DIR/scripts"
DISPATCH_SH="$SCRIPTS_DIR/dispatch-feature-tdd.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

FIND_FEATURE_SH="$(cd "$SCRIPT_DIR/../.." && pwd)/contract/scripts/find-feature.sh"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# Build a minimal RABBIT_ROOT fixture with find-feature.sh + one feature.
make_rabbit_root() {
  local root="$1"
  mkdir -p "$root/.claude/features/tdd-state-machine/docs/spec"
  mkdir -p "$root/.claude/features/contract/scripts"

  # Copy find-feature.sh so dispatch-feature-tdd.sh can locate the feature.
  cp "$FIND_FEATURE_SH" "$root/.claude/features/contract/scripts/find-feature.sh"

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
# t1: --linked-item --item-type bug is accepted (replaces old --bug)
# ---------------------------------------------------------------------------
t1() {
  local root="$TMPROOT/t1_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /some/bug/dir --item-type bug 2>&1)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t1: --linked-item --item-type bug accepted, exits 0 with non-empty stdout"
  else
    ko "t1: rc=$rc; expected 0. stderr/stdout: $out"
  fi
}

# ---------------------------------------------------------------------------
# t2: --linked-item --item-type backlog is accepted (replaces old --backlog)
# ---------------------------------------------------------------------------
t2() {
  local root="$TMPROOT/t2_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /some/backlog/item --item-type backlog 2>&1)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t2: --linked-item --item-type backlog accepted, exits 0 with non-empty stdout"
  else
    ko "t2: rc=$rc; expected 0. stderr/stdout: $out"
  fi
}

# ---------------------------------------------------------------------------
# t3: when --linked-item bug is given, emitted prompt contains tdd-report.json
# ---------------------------------------------------------------------------
t3() {
  local root="$TMPROOT/t3_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /bugs/my-bug --item-type bug 2>/dev/null)
  if echo "$out" | grep -q "tdd-report.json"; then
    ok "t3: prompt contains 'tdd-report.json'"
  else
    ko "t3: 'tdd-report.json' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t4: when --linked-item bug is given, emitted prompt contains the bug dir path
# ---------------------------------------------------------------------------
t4() {
  local root="$TMPROOT/t4_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /bugs/my-bug --item-type bug 2>/dev/null)
  if echo "$out" | grep -q "/bugs/my-bug"; then
    ok "t4: prompt contains the linked-item dir path"
  else
    ko "t4: linked-item dir path '/bugs/my-bug' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t5: when --linked-item bug is given, emitted prompt contains spec_compliance
# ---------------------------------------------------------------------------
t5() {
  local root="$TMPROOT/t5_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /bugs/my-bug --item-type bug 2>/dev/null)
  if echo "$out" | grep -q "spec_compliance"; then
    ok "t5: prompt contains 'spec_compliance' field"
  else
    ko "t5: 'spec_compliance' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t6: when --linked-item backlog is given, emitted prompt contains tdd-report.json
# ---------------------------------------------------------------------------
t6() {
  local root="$TMPROOT/t6_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /backlogs/my-item --item-type backlog 2>/dev/null)
  if echo "$out" | grep -q "tdd-report.json"; then
    ok "t6: prompt contains 'tdd-report.json'"
  else
    ko "t6: 'tdd-report.json' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t7: when --linked-item backlog is given, emitted prompt contains the item dir path
# ---------------------------------------------------------------------------
t7() {
  local root="$TMPROOT/t7_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /backlogs/my-item --item-type backlog 2>/dev/null)
  if echo "$out" | grep -q "/backlogs/my-item"; then
    ok "t7: prompt contains the linked-item dir path"
  else
    ko "t7: backlog item dir path '/backlogs/my-item' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t8: when --linked-item backlog is given, emitted prompt contains test_gap_analysis
# ---------------------------------------------------------------------------
t8() {
  local root="$TMPROOT/t8_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /backlogs/my-item --item-type backlog 2>/dev/null)
  if echo "$out" | grep -q "test_gap_analysis"; then
    ok "t8: prompt contains 'test_gap_analysis' field"
  else
    ko "t8: 'test_gap_analysis' not found in prompt"
  fi
}

# ---------------------------------------------------------------------------
# t9: when neither --linked-item nor --item-type is given, prompt is still valid
# ---------------------------------------------------------------------------
t9() {
  local root="$TMPROOT/t9_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" 2>&1)
  local rc=$?
  if [ "$rc" = "0" ] && [ -n "$out" ]; then
    ok "t9: baseline (no --linked-item) still exits 0"
  else
    ko "t9: baseline broke: rc=$rc"
  fi
}

# ---------------------------------------------------------------------------
# t10: emitted prompt contains HANDOFF section
# ---------------------------------------------------------------------------
t10() {
  local root="$TMPROOT/t10_root"
  make_rabbit_root "$root"
  local out
  out=$(RABBIT_ROOT="$root" bash "$DISPATCH_SH" tdd-state-machine "add feature" --linked-item /bugs/my-bug --item-type bug 2>/dev/null)
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
