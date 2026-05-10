#!/usr/bin/env bash
# test-RABBIT-CAGE-11-feature-touch-skill.sh
# Verifies the rabbit-feature-touch skill exists and is correctly formed.
# R3-compliant: no interactive constructs, prints PASS/FAIL per assertion, exits 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SKILL_MD="${REPO_ROOT}/.claude/features/rabbit-cage/skills/rabbit-feature-touch/SKILL.md"
FEATURE_JSON="${REPO_ROOT}/.claude/features/rabbit-cage/feature.json"

FAILURES=0

assert() {
  local label="$1"
  local result="$2"
  if [ "$result" = "0" ]; then
    echo "PASS: ${label}"
  else
    echo "FAIL: ${label}"
    FAILURES=$(( FAILURES + 1 ))
  fi
}

# 1. SKILL.md exists
[ -f "${SKILL_MD}" ]
assert "SKILL.md exists at skills/rabbit-feature-touch/SKILL.md" "$?"

# 2. SKILL.md has YAML frontmatter (contains "name:" and "description:")
grep -q "^name:" "${SKILL_MD}" 2>/dev/null
assert "SKILL.md has frontmatter 'name:' field" "$?"

grep -q "^description:" "${SKILL_MD}" 2>/dev/null
assert "SKILL.md has frontmatter 'description:' field" "$?"

# 3. frontmatter name field equals "rabbit-feature-touch"
grep -q "^name: rabbit-feature-touch" "${SKILL_MD}" 2>/dev/null
assert "frontmatter name equals 'rabbit-feature-touch'" "$?"

# 4. description starts with "Use when"
grep -q "^description: Use when" "${SKILL_MD}" 2>/dev/null
assert "description starts with 'Use when'" "$?"

# 5. body mentions tdd-step.sh
grep -q "tdd-step.sh" "${SKILL_MD}" 2>/dev/null
assert "body mentions 'tdd-step.sh'" "$?"

# 6. body mentions dispatch-feature-edit.sh
grep -q "dispatch-feature-edit.sh" "${SKILL_MD}" 2>/dev/null
assert "body mentions 'dispatch-feature-edit.sh'" "$?"

# 7. body mentions --force
grep -q "\-\-force" "${SKILL_MD}" 2>/dev/null
assert "body mentions '--force'" "$?"

# 8. feature.json surface.skills contains "rabbit-feature-touch"
python3 -c "
import json, sys
with open('${FEATURE_JSON}') as f:
    d = json.load(f)
skills = d.get('surface', {}).get('skills', [])
sys.exit(0 if 'rabbit-feature-touch' in skills else 1)
" 2>/dev/null
assert "feature.json surface.skills contains 'rabbit-feature-touch'" "$?"

# Final result
echo ""
if [ "${FAILURES}" -eq 0 ]; then
  echo "ALL TESTS PASSED"
  exit 0
else
  echo "${FAILURES} TEST(S) FAILED"
  exit 1
fi
