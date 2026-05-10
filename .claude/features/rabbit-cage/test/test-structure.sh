#!/usr/bin/env bash
# rabbit-cage structure tests
# Tests that rabbit-cage directory layout is correct.
# All tests must FAIL before implementation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CAGE_DIR="$REPO_ROOT/.claude/features/rabbit-cage"

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

# t1: agents/ exists as a directory
if [ -d "$CAGE_DIR/agents" ]; then ok 1 "agents/ exists as directory"; else fail_t 1 "agents/ does not exist or is not a directory"; fi

# t2: commands/ exists as a directory
if [ -d "$CAGE_DIR/commands" ]; then ok 2 "commands/ exists as directory"; else fail_t 2 "commands/ does not exist or is not a directory"; fi

# t3: hooks/ exists as a directory
if [ -d "$CAGE_DIR/hooks" ]; then ok 3 "hooks/ exists as directory"; else fail_t 3 "hooks/ does not exist or is not a directory"; fi

# t4: skills/ exists as a directory
if [ -d "$CAGE_DIR/skills" ]; then ok 4 "skills/ exists as directory"; else fail_t 4 "skills/ does not exist or is not a directory"; fi

# t5: settings.json exists and is valid JSON
if [ -f "$CAGE_DIR/settings.json" ] && python3 -c "import sys,json; json.load(open('$CAGE_DIR/settings.json'))" 2>/dev/null; then
    ok 5 "settings.json exists and is valid JSON"
else
    fail_t 5 "settings.json missing or invalid JSON"
fi

# t6: CLAUDE.md exists (moved from root-management)
if [ -f "$CAGE_DIR/CLAUDE.md" ]; then ok 6 "CLAUDE.md exists in rabbit-cage"; else fail_t 6 "CLAUDE.md not found in rabbit-cage"; fi

# t7: README.md exists
if [ -f "$CAGE_DIR/README.md" ]; then ok 7 "README.md exists in rabbit-cage"; else fail_t 7 "README.md not found in rabbit-cage"; fi

# t8: install.sh exists and is executable
if [ -f "$CAGE_DIR/install.sh" ] && [ -x "$CAGE_DIR/install.sh" ]; then ok 8 "install.sh exists and is executable"; else fail_t 8 "install.sh missing or not executable"; fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
