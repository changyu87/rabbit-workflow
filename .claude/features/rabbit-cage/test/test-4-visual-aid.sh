#!/usr/bin/env bash
# test-4-visual-aid.sh
# Verifies workspace-tree.sh script, rabbit-workspace skill, and feature.json registration.
# R3-compliant: no interactive constructs, prints PASS/FAIL per assertion, exits 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SCRIPT="${REPO_ROOT}/.claude/features/rabbit-cage/scripts/workspace-tree.sh"
SKILL_MD="${REPO_ROOT}/.claude/features/rabbit-cage/skills/rabbit-workspace/SKILL.md"
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

# 1. workspace-tree.sh exists and is executable
[ -x "${SCRIPT}" ]
assert "scripts/workspace-tree.sh exists and is executable" "$?"

# 2. Running workspace-tree.sh exits 0
"${SCRIPT}" >/dev/null 2>&1
assert "workspace-tree.sh exits 0" "$?"

# 3. Output contains ".claude"
"${SCRIPT}" 2>/dev/null | grep -q "\.claude"
assert "workspace-tree.sh output contains '.claude'" "$?"

# 4. Output contains "features"
"${SCRIPT}" 2>/dev/null | grep -q "features"
assert "workspace-tree.sh output contains 'features'" "$?"

# 5. Output contains "#" (annotations present)
"${SCRIPT}" 2>/dev/null | grep -q "#"
assert "workspace-tree.sh output contains '#' annotations" "$?"

# 6. Running workspace-tree.sh --full exits 0
"${SCRIPT}" --full >/dev/null 2>&1
assert "workspace-tree.sh --full exits 0" "$?"

# 7. skills/rabbit-workspace/SKILL.md exists
[ -f "${SKILL_MD}" ]
assert "skills/rabbit-workspace/SKILL.md exists" "$?"

# 8. SKILL.md frontmatter has name: rabbit-workspace and description starts with "Use when"
grep -q "^name: rabbit-workspace" "${SKILL_MD}" 2>/dev/null
assert "SKILL.md frontmatter name equals 'rabbit-workspace'" "$?"

grep -q "^description: Use when" "${SKILL_MD}" 2>/dev/null
assert "SKILL.md description starts with 'Use when'" "$?"

# 9. feature.json surface.skills contains "rabbit-workspace"
python3 -c "
import json, sys
with open('${FEATURE_JSON}') as f:
    d = json.load(f)
skills = d.get('surface', {}).get('skills', [])
sys.exit(0 if 'rabbit-workspace' in skills else 1)
" 2>/dev/null
assert "feature.json surface.skills contains 'rabbit-workspace'" "$?"

# Final result
echo ""
if [ "${FAILURES}" -eq 0 ]; then
  echo "ALL TESTS PASSED"
  exit 0
else
  echo "${FAILURES} TEST(S) FAILED"
  exit 1
fi
