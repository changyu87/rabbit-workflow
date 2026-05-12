#!/bin/bash
# Tests that SKILL.md contains the confirm-token bypass path section.
# These tests are expected to FAIL before the section is added to SKILL.md.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
SKILL_MD="$REPO_ROOT/.claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md"

PASS=0; FAIL=0
ok() { echo "  ok   $*"; PASS=$((PASS+1)); }
ko() { echo "  FAIL $*"; FAIL=$((FAIL+1)); }

# t1: SKILL.md contains the "Override Path" section header
t1() {
  if ! [ -f "$SKILL_MD" ]; then
    ko "t1: $SKILL_MD not found"
    return
  fi
  if grep -q "## Override Path" "$SKILL_MD" 2>/dev/null; then
    ok "t1: SKILL.md contains '## Override Path' section header"
  else
    ko "t1: SKILL.md missing '## Override Path' section header"
  fi
}

# t2: SKILL.md mentions the confirm token presentation step
t2() {
  if ! [ -f "$SKILL_MD" ]; then
    ko "t2: $SKILL_MD not found"
    return
  fi
  if grep -q "confirm token" "$SKILL_MD" 2>/dev/null; then
    ok "t2: SKILL.md mentions 'confirm token'"
  else
    ko "t2: SKILL.md missing 'confirm token' reference"
  fi
}

# t3: SKILL.md documents the one-time override choice
t3() {
  if ! [ -f "$SKILL_MD" ]; then
    ko "t3: $SKILL_MD not found"
    return
  fi
  if grep -q "one-time" "$SKILL_MD" 2>/dev/null; then
    ok "t3: SKILL.md documents 'one-time' override choice"
  else
    ko "t3: SKILL.md missing 'one-time' override choice"
  fi
}

# t4: SKILL.md documents the session override choice
t4() {
  if ! [ -f "$SKILL_MD" ]; then
    ko "t4: $SKILL_MD not found"
    return
  fi
  if grep -q "session" "$SKILL_MD" 2>/dev/null; then
    ok "t4: SKILL.md documents 'session' override choice"
  else
    ko "t4: SKILL.md missing 'session' override choice"
  fi
}

# t5: SKILL.md documents .rabbit-scope-override file writing
t5() {
  if ! [ -f "$SKILL_MD" ]; then
    ko "t5: $SKILL_MD not found"
    return
  fi
  if grep -q "\.rabbit-scope-override" "$SKILL_MD" 2>/dev/null; then
    ok "t5: SKILL.md references '.rabbit-scope-override' file"
  else
    ko "t5: SKILL.md missing '.rabbit-scope-override' reference"
  fi
}

# t6: SKILL.md states that user approval IS the authorization
t6() {
  if ! [ -f "$SKILL_MD" ]; then
    ko "t6: $SKILL_MD not found"
    return
  fi
  if grep -q "approval" "$SKILL_MD" 2>/dev/null; then
    ok "t6: SKILL.md mentions user approval as authorization"
  else
    ko "t6: SKILL.md missing user approval authorization statement"
  fi
}

echo "running confirm-token bypass section tests"
t1; t2; t3; t4; t5; t6
echo
echo "summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
