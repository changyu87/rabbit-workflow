#!/usr/bin/env bash
# Tests that SKILL.md exists and contains all required sections.
set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL="$FEATURE_DIR/skills/rabbit-file/SKILL.md"

pass=0; fail=0
assert_pass() { echo "PASS: $1"; pass=$((pass+1)); }
assert_fail() { echo "FAIL: $1 — $2"; fail=$((fail+1)); }

# t1: SKILL.md exists
if [ -f "$SKILL" ]; then assert_pass "SKILL.md exists"
else assert_fail "SKILL.md exists" "missing at $SKILL"; fi

# t2-t6: Required sections
for section in "## Overview" "## File Protocol" "## Work Protocol" "## List Protocol" "## branch_ops.py Lifecycle"; do
    if grep -qF "$section" "$SKILL" 2>/dev/null; then
        assert_pass "contains '$section'"
    else
        assert_fail "contains '$section'" "section not found in SKILL.md"
    fi
done

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
