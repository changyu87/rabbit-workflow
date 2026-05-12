#!/bin/bash
# Tests for rabbit-feature-touch skill ownership migration from rabbit-cage to tdd-state-machine.
# All assertions are expected to FAIL until implementation is complete.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
FEATURES_DIR="$REPO_ROOT/.claude/features"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: tdd-state-machine/skills/rabbit-feature-touch/ directory exists
t1() {
  local skill_dir="$FEATURES_DIR/tdd-state-machine/skills/rabbit-feature-touch"
  if [ -d "$skill_dir" ]; then
    ok "t1: $skill_dir exists"
  else
    ko "t1: $skill_dir does not exist"
  fi
}

# t2: tdd-state-machine/skills/rabbit-feature-touch/SKILL.md exists
t2() {
  local skill_md="$FEATURES_DIR/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md"
  if [ -f "$skill_md" ]; then
    ok "t2: $skill_md exists"
  else
    ko "t2: $skill_md does not exist"
  fi
}

# t3: tdd-state-machine/feature.json surface.skills includes "rabbit-feature-touch"
t3() {
  local feature_json="$FEATURES_DIR/tdd-state-machine/feature.json"
  if ! [ -f "$feature_json" ]; then
    ko "t3: $feature_json not found"
    return
  fi
  local found
  found=$(jq -r '.surface.skills // [] | map(select(. == "rabbit-feature-touch")) | length' "$feature_json" 2>/dev/null)
  if [ "$found" = "1" ]; then
    ok "t3: tdd-state-machine/feature.json surface.skills includes rabbit-feature-touch"
  else
    ko "t3: tdd-state-machine/feature.json surface.skills does NOT include rabbit-feature-touch (found=$found)"
  fi
}

# t4: rabbit-cage/feature.json surface.skills does NOT include "rabbit-feature-touch"
t4() {
  local feature_json="$FEATURES_DIR/rabbit-cage/feature.json"
  if ! [ -f "$feature_json" ]; then
    ko "t4: $feature_json not found"
    return
  fi
  local found
  found=$(jq -r '.surface.skills // [] | map(select(. == "rabbit-feature-touch")) | length' "$feature_json" 2>/dev/null)
  if [ "$found" = "0" ]; then
    ok "t4: rabbit-cage/feature.json surface.skills does NOT include rabbit-feature-touch"
  else
    ko "t4: rabbit-cage/feature.json surface.skills still includes rabbit-feature-touch (found=$found)"
  fi
}

# t5: if .claude/skills/rabbit-feature-touch/SKILL.md exists, its content matches
#     tdd-state-machine/skills/rabbit-feature-touch/SKILL.md
t5() {
  local deployed="$REPO_ROOT/.claude/skills/rabbit-feature-touch/SKILL.md"
  local source="$FEATURES_DIR/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md"

  if ! [ -f "$deployed" ]; then
    ok "t5: .claude/skills/rabbit-feature-touch/SKILL.md absent — nothing to compare (skip)"
    return
  fi
  if ! [ -f "$source" ]; then
    ko "t5: source $source missing; cannot verify deployed SKILL.md was sourced from tdd-state-machine"
    return
  fi
  if diff -q "$source" "$deployed" >/dev/null 2>&1; then
    ok "t5: deployed SKILL.md matches tdd-state-machine source"
  else
    ko "t5: deployed SKILL.md differs from tdd-state-machine source (content mismatch)"
  fi
}

echo "running rabbit-feature-touch skill ownership tests"
t1; t2; t3; t4; t5
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
