#!/usr/bin/env bash
# rabbit-cage structure tests
# Tests that rabbit-cage directory layout is correct.
# All tests must FAIL before implementation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CAGE_DIR="$REPO_ROOT/.claude/features/rabbit-cage"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

echo "test-structure.sh"

# t1: agents/ does NOT exist (removed from rabbit-cage surface — agents are gone)
if [ ! -e "$CAGE_DIR/agents" ]; then ok 1 "agents/ does not exist or is not a directory"; else fail_t 1 "agents/ still exists — must be removed from rabbit-cage"; fi

# t2: commands/ exists as a directory
if [ -d "$CAGE_DIR/commands" ]; then ok 2 "commands/ exists as directory"; else fail_t 2 "commands/ does not exist or is not a directory"; fi

# t3: hooks/ exists as a directory
if [ -d "$CAGE_DIR/hooks" ]; then ok 3 "hooks/ exists as directory"; else fail_t 3 "hooks/ does not exist or is not a directory"; fi

# t4: skills/ does NOT exist in rabbit-cage (skill ownership moved to tdd-state-machine)
if [ ! -d "$CAGE_DIR/skills" ]; then ok 4 "skills/ does not exist in rabbit-cage (correctly moved to tdd-state-machine)"; else fail_t 4 "skills/ still exists in rabbit-cage — orphan dir should be removed"; fi

# t5: settings.json exists and is valid JSON
if [ -f "$CAGE_DIR/settings.json" ] && python3 -c "import sys,json; json.load(open('$CAGE_DIR/settings.json'))" 2>/dev/null; then
    ok 5 "settings.json exists and is valid JSON"
else
    fail_t 5 "settings.json missing or invalid JSON"
fi

# t6: policy-header.json exists in rabbit-cage (replaces CLAUDE.md — machine-readable header source)
if [ -f "$SCRIPT_DIR/../policy-header.json" ]; then
    ok 6 "policy-header.json exists in rabbit-cage"
else
    fail_t 6 "policy-header.json does not exist in rabbit-cage"
fi

# t7: README.md exists
if [ -f "$CAGE_DIR/README.md" ]; then ok 7 "README.md exists in rabbit-cage"; else fail_t 7 "README.md not found in rabbit-cage"; fi

# t8: install.sh exists and is executable
if [ -f "$CAGE_DIR/install.sh" ] && [ -x "$CAGE_DIR/install.sh" ]; then ok 8 "install.sh exists and is executable"; else fail_t 8 "install.sh missing or not executable"; fi

# t9: CLAUDE.md does NOT exist in rabbit-cage (replaced by policy-header.json)
if [ ! -f "$SCRIPT_DIR/../CLAUDE.md" ]; then
    ok 9 "CLAUDE.md does not exist in rabbit-cage (replaced by policy-header.json)"
else
    fail_t 9 "CLAUDE.md still exists in rabbit-cage — should be replaced by policy-header.json"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
