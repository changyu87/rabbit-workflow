#!/bin/bash
# Test the opus-for-planning-agents enforcement.
# Strategy: build fixture agent files in a temp .claude/agents/ and run the check.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECK="$FEATURE_DIR/scripts/check-opus-for-planning-agents.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT INT TERM

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

mkdir -p "$TMPROOT/agents"
export AGENTS_DIR="$TMPROOT/agents"

mk_agent() {
  local name="$1" desc="$2" model="$3"
  cat > "$AGENTS_DIR/$name.md" <<EOF
---
name: $name
description: $desc
tools: Read, Bash
model: $model
---
body
EOF
}

# t1: planning agent with model=opus -> ok
rm -f "$AGENTS_DIR"/*.md
mk_agent "planner" "Brainstorming and planning agent" "opus"
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" = "0" ] && ok "t1: planner (opus) -> ok" \
  || ko "t1: rc=$rc out=$out"

# t2: planning agent with model=sonnet -> fails
rm -f "$AGENTS_DIR"/*.md
mk_agent "planner" "Brainstorming and planning agent" "sonnet"
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" != "0" ] && echo "$out" | grep -qi "planner" \
  && ok "t2: planner (sonnet) -> fails" \
  || ko "t2: rc=$rc out=$out"

# t3: non-planning agent with model=sonnet -> ok
rm -f "$AGENTS_DIR"/*.md
mk_agent "logger" "Reads logs and emits a structured summary" "sonnet"
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" = "0" ] && ok "t3: non-planning (sonnet) -> ok" \
  || ko "t3: rc=$rc out=$out"

# t4: spec-writing agent with model=haiku -> fails
rm -f "$AGENTS_DIR"/*.md
mk_agent "speccer" "Spec-writing subagent" "haiku"
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" != "0" ] && echo "$out" | grep -qi "speccer" \
  && ok "t4: spec-writing (haiku) -> fails" \
  || ko "t4: rc=$rc out=$out"

# t5: planning agent with NO model line -> fails (must be explicit opus)
rm -f "$AGENTS_DIR"/*.md
cat > "$AGENTS_DIR/loose.md" <<EOF
---
name: loose
description: Brainstorming agent with no explicit model
tools: Read, Bash
---
body
EOF
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" != "0" ] && echo "$out" | grep -qi "loose" \
  && ok "t5: planning agent without explicit model -> fails" \
  || ko "t5: rc=$rc out=$out"

# t6: empty agents dir -> ok (vacuously)
rm -f "$AGENTS_DIR"/*.md
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" = "0" ] && ok "t6: empty agents dir -> ok" \
  || ko "t6: rc=$rc out=$out"

# t7: mix - planner ok, speccer fails -> overall fails and names speccer only
rm -f "$AGENTS_DIR"/*.md
mk_agent "planner" "planning subagent" "opus"
mk_agent "speccer" "spec-writing agent" "sonnet"
out=$("$CHECK" 2>&1); rc=$?
[ "$rc" != "0" ] && echo "$out" | grep -qi "speccer" && ! echo "$out" | grep -qi "planner.*violat" \
  && ok "t7: mix - only speccer flagged" \
  || ko "t7: rc=$rc out=$out"

echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
