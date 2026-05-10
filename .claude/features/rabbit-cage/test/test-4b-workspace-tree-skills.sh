#!/usr/bin/env bash
# test-4b-workspace-tree-skills.sh
# Verifies workspace-tree.sh default mode shows skill dirs inside skills/.
# R3-compliant: no interactive constructs, prints PASS/FAIL per assertion, exits 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SCRIPT="${REPO_ROOT}/.claude/features/rabbit-cage/scripts/workspace-tree.sh"

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

OUTPUT="$("${SCRIPT}" 2>/dev/null)"

# 1. Output contains "rabbit-feature-touch" (skill dir inside skills/)
echo "${OUTPUT}" | grep -q "rabbit-feature-touch"
assert "workspace-tree.sh output contains 'rabbit-feature-touch'" "$?"

# 2. Output contains "rabbit-workspace" as a skill directory (not just annotation text)
echo "${OUTPUT}" | grep -q "rabbit-workspace/"
assert "workspace-tree.sh output contains 'rabbit-workspace/'" "$?"

# 3. Output contains "SKILL.md" (the skill definition file inside a skill dir)
echo "${OUTPUT}" | grep -q "SKILL.md"
assert "workspace-tree.sh output contains 'SKILL.md'" "$?"

# Final result
echo ""
if [ "${FAILURES}" -eq 0 ]; then
  echo "ALL TESTS PASSED"
  exit 0
else
  echo "${FAILURES} TEST(S) FAILED"
  exit 1
fi
