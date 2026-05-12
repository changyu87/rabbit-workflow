#!/usr/bin/env bash
# test-bug-surface-skills.sh
# Asserts that surface.skills in feature.json is empty ([]).
# Skills are now managed via build-contract.json copy-file entries;
# the surface.skills declaration in feature.json is retired.
#
# t_skills1: surface.skills must be []
#
# Exit: 1 if any assertion fails.

set -uo pipefail

FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FEATURE_JSON="$FEATURE_DIR/feature.json"

pass=0
fail=0

assert_pass() {
    local label="$1"
    echo "PASS: $label"
    pass=$((pass + 1))
}

assert_fail() {
    local label="$1"
    local reason="$2"
    echo "FAIL: $label — $reason"
    fail=$((fail + 1))
}

# ---------------------------------------------------------------------------
# t_skills1: surface.skills must be []
# ---------------------------------------------------------------------------
T_SKILLS1_LABEL="t_skills1: surface.skills in feature.json must be []"

SKILLS_VAL="$(jq -c '.surface.skills // "MISSING"' "$FEATURE_JSON" 2>/dev/null)"

if [ "$SKILLS_VAL" = "[]" ]; then
    assert_pass "$T_SKILLS1_LABEL"
else
    assert_fail "$T_SKILLS1_LABEL" "surface.skills=$SKILLS_VAL (expected [])"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Results: $pass passed, $fail failed"

if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
