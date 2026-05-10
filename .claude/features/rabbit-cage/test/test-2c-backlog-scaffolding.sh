#!/usr/bin/env bash
# test-2c-backlog-scaffolding.sh
# Verifies that the docs/backlog/ scaffolding, backlog scripts, and contract
# updates for the backlog feature exist.
# R3-compliant: no interactive constructs, prints PASS/FAIL per assertion, exits 1 on any failure.
#
# NOTE: All assertions are expected to FAIL until the impl leg creates these artifacts.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
CAGE_DIR="${REPO_ROOT}/.claude/features/rabbit-cage"
CONTRACT="${CAGE_DIR}/docs/spec/contract.md"

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

# 1. docs/backlog/ directory exists
[ -d "${CAGE_DIR}/docs/backlog" ]
assert "docs/backlog/ directory exists" "$?"

# 2. docs/backlog/backlog-contract.md exists
[ -f "${CAGE_DIR}/docs/backlog/backlog-contract.md" ]
assert "docs/backlog/backlog-contract.md exists" "$?"

# 3. backlog-contract.md contains "open" (valid status value)
grep -q "open" "${CAGE_DIR}/docs/backlog/backlog-contract.md" 2>/dev/null
assert "backlog-contract.md contains status value \"open\"" "$?"

# 4. backlog-contract.md contains "done" (valid status value)
grep -q "done" "${CAGE_DIR}/docs/backlog/backlog-contract.md" 2>/dev/null
assert "backlog-contract.md contains status value \"done\"" "$?"

# 5. scripts/file-backlog-item.sh exists and is executable
[ -f "${CAGE_DIR}/scripts/file-backlog-item.sh" ] && [ -x "${CAGE_DIR}/scripts/file-backlog-item.sh" ]
assert "scripts/file-backlog-item.sh exists and is executable" "$?"

# 6. scripts/backlog-item-status.sh exists and is executable
[ -f "${CAGE_DIR}/scripts/backlog-item-status.sh" ] && [ -x "${CAGE_DIR}/scripts/backlog-item-status.sh" ]
assert "scripts/backlog-item-status.sh exists and is executable" "$?"

# 7. contract.md provides.scripts mentions "file-backlog-item.sh"
grep -q "file-backlog-item.sh" "${CONTRACT}" 2>/dev/null
assert "contract.md provides.scripts mentions \"file-backlog-item.sh\"" "$?"

# 8. contract.md provides.schemas is non-empty (not [])
# Extract the "schemas" value and confirm it is not an empty JSON array
python3 - "${CONTRACT}" <<PYEOF 2>/dev/null
import sys, json, re

contract_path = sys.argv[1]
try:
    with open(contract_path) as f:
        text = f.read()
    # Extract the fenced JSON block
    m = re.search(r'\x60\x60\x60json\s*(.*?)\s*\x60\x60\x60', text, re.DOTALL)
    if not m:
        sys.exit(1)
    data = json.loads(m.group(1))
    schemas = data.get("provides", {}).get("schemas", [])
    sys.exit(0 if schemas else 1)
except Exception:
    sys.exit(1)
PYEOF
assert "contract.md provides.schemas is non-empty (not [])" "$?"

# Final result
echo ""
if [ "${FAILURES}" -eq 0 ]; then
  echo "ALL TESTS PASSED"
  exit 0
else
  echo "${FAILURES} TEST(S) FAILED"
  exit 1
fi
