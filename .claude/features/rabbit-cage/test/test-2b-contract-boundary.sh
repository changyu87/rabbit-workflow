#!/usr/bin/env bash
# test-2b-contract-boundary.sh
# Verifies that contract.md declares the rabbit-feature-touch skill, invokes
# dispatch-feature-edit.sh, and contains a prose boundary clarification section.
# R3-compliant: no interactive constructs, prints PASS/FAIL per assertion, exits 1 on any failure.
#
# NOTE: These assertions are expected to FAIL until contract.md is updated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
CONTRACT="${REPO_ROOT}/.claude/features/rabbit-cage/docs/spec/contract.md"

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

# 1. contract.md contains "rabbit-feature-touch" in the provides.skills array.
#    Currently "skills": [] (empty) — will FAIL until the skill is added.
grep -q '"rabbit-feature-touch"' "${CONTRACT}" 2>/dev/null
assert "contract.md contains \"rabbit-feature-touch\" in provides.skills" "$?"

# 2. contract.md lists dispatch-feature-edit.sh in invokes.scripts.
#    Currently only relink.sh is listed — will FAIL until the script is added.
grep -q "dispatch-feature-edit.sh" "${CONTRACT}" 2>/dev/null
assert "contract.md invokes dispatch-feature-edit.sh in invokes.scripts" "$?"

# 3. contract.md contains a prose section (outside the fenced JSON block) that mentions
#    "boundary" or "dispatch-feature-edit".  Uses Python to strip the JSON fence first.
CONTRACT_PATH="${CONTRACT}" python3 - <<'PYEOF' 2>/dev/null
import sys, os

contract_path = os.environ["CONTRACT_PATH"]
with open(contract_path) as f:
    lines = f.readlines()

inside_json = False
prose_lines = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith("```json"):
        inside_json = True
        continue
    if inside_json and stripped == "```":
        inside_json = False
        continue
    if not inside_json:
        prose_lines.append(line)

prose = "".join(prose_lines)
sys.exit(0 if ("boundary" in prose or "dispatch-feature-edit" in prose) else 1)
PYEOF
assert "contract.md prose (outside JSON block) mentions 'boundary' or 'dispatch-feature-edit'" "$?"

# Final result
echo ""
if [ "${FAILURES}" -eq 0 ]; then
  echo "ALL TESTS PASSED"
  exit 0
else
  echo "${FAILURES} TEST(S) FAILED"
  exit 1
fi
