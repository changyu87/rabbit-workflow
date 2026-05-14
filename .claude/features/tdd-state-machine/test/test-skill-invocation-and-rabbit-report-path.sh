#!/bin/bash
# test-skill-invocation-and-rabbit-report-path.sh
# Tests for:
#   Fix 1 (TDD-STATE-MACHINE-1): SKILL.md Step 1 uses Skill() tool invocation
#   Fix 2 (TDD-STATE-MACHINE-BACKLOG-2): dispatch-feature-tdd.sh writes to .rabbit/ path
set -u
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL="$REPO_ROOT/.claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md"
DISPATCH="$REPO_ROOT/.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh"
GITIGNORE="$REPO_ROOT/.gitignore"
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# Fix 1: SKILL.md Step 1 must use Skill() invocation, not direct resolve-scope.sh shell call
grep -q 'Skill("rabbit-feature-scope"' "$SKILL" \
  && ok "SKILL.md Step 1 uses Skill() tool invocation" \
  || fail "SKILL.md Step 1 missing Skill() tool invocation"

grep -qE 'resolve-scope\.sh' "$SKILL" \
  && fail "SKILL.md Step 1 still references resolve-scope.sh shell call" \
  || ok "SKILL.md Step 1 does not reference resolve-scope.sh"

# Fix 2a: dispatch-feature-tdd.sh must write tdd-report.json to .rabbit/ path
prompt=$("$DISPATCH" contract "test request" 2>/dev/null)
echo "$prompt" | grep -q '\.rabbit/tdd-report\.json' \
  && ok "dispatch-feature-tdd.sh prompt references .rabbit/tdd-report.json" \
  || fail "dispatch-feature-tdd.sh prompt does not reference .rabbit/tdd-report.json"

# Fix 2b: dispatch-feature-tdd.sh must NOT reference bare repo-root tdd-report.json path (e.g. REPO_ROOT/tdd-report.json)
echo "$prompt" | grep -qE '\$\{REPO_ROOT\}/tdd-report\.json|REPO_ROOT\}/tdd-report\.json' \
  && fail "dispatch-feature-tdd.sh prompt still references bare repo-root tdd-report.json" \
  || ok "dispatch-feature-tdd.sh prompt does not reference bare repo-root tdd-report.json"

# Fix 2c: dispatch-feature-tdd.sh must contain mkdir -p for .rabbit/
grep -q 'mkdir -p' "$DISPATCH" && grep -q '\.rabbit' "$DISPATCH" \
  && ok "dispatch-feature-tdd.sh contains mkdir -p for .rabbit/" \
  || fail "dispatch-feature-tdd.sh missing mkdir -p .rabbit/"

# Fix 2d: .gitignore must list .rabbit/
grep -qE '^\.rabbit/' "$GITIGNORE" \
  && ok ".gitignore contains .rabbit/" \
  || fail ".gitignore missing .rabbit/"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
