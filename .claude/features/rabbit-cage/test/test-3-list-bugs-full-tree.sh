#!/usr/bin/env bash
# test-3-list-bugs-full-tree.sh
# Verifies that list-bugs.sh scans the full repo tree via feature.json
# files to find bugs_root directories, rather than reading from a single
# hardcoded BUG_ROOT.
#
# All four assertions are expected to FAIL against the current list-bugs.sh
# because the current script reads from .claude/docs/bugs (wrong root)
# instead of scanning feature.json files.
#
# Exit: 1 if any assertion fails (expected: all 4 fail → exit 1).

set -uo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
SCRIPT="$REPO_ROOT/.claude/features/rabbit-cage/scripts/list-bugs.sh"

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
# Assertion 1: no-args JSON includes RABBIT-CAGE-1 from rabbit-cage bugs_root
#
# Expected behavior (post-fix): script finds .claude/features/rabbit-cage/feature.json,
#   reads its bugs_root, collects all bugs, and returns RABBIT-CAGE-1 in JSON.
# Current behavior: script reads from .claude/docs/bugs (old hardcoded default),
#   which does not contain RABBIT-CAGE-1 → empty array or no match → FAIL.
# ---------------------------------------------------------------------------
A1_LABEL="A1: no-args JSON includes RABBIT-CAGE-1 from rabbit-cage bugs_root"

output1="$(cd "$REPO_ROOT" && bash "$SCRIPT" 2>&1)"
exit1=$?

if [ $exit1 -ne 0 ]; then
    assert_fail "$A1_LABEL" "script exited with code $exit1"
elif echo "$output1" | jq -e '[ .[] | select(.name == "RABBIT-CAGE-1") ] | length > 0' > /dev/null 2>&1; then
    assert_pass "$A1_LABEL"
else
    assert_fail "$A1_LABEL" "RABBIT-CAGE-1 not present in output (output: $(echo "$output1" | head -c 200))"
fi

# ---------------------------------------------------------------------------
# Assertion 2: --feature rabbit-cage returns bugs with related_feature == "rabbit-cage"
#
# Expected behavior (post-fix): reads correct bugs_root → non-empty, all with
#   related_feature == "rabbit-cage".
# Current behavior: reads from wrong root → empty [] → FAIL (zero bugs returned).
# ---------------------------------------------------------------------------
A2_LABEL="A2: --feature rabbit-cage returns non-empty result with related_feature=rabbit-cage"

output2="$(cd "$REPO_ROOT" && bash "$SCRIPT" --feature rabbit-cage 2>&1)"
exit2=$?

if [ $exit2 -ne 0 ]; then
    assert_fail "$A2_LABEL" "script exited with code $exit2"
else
    count2="$(echo "$output2" | jq 'length' 2>/dev/null || echo 0)"
    if [ "$count2" -gt 0 ]; then
        # Also verify all returned bugs actually have related_feature == rabbit-cage
        wrong="$(echo "$output2" | jq '[ .[] | select(.related_feature != "rabbit-cage") ] | length' 2>/dev/null || echo 1)"
        if [ "$wrong" -eq 0 ]; then
            assert_pass "$A2_LABEL"
        else
            assert_fail "$A2_LABEL" "output contains bugs with wrong related_feature"
        fi
    else
        assert_fail "$A2_LABEL" "output is empty — expected bugs for rabbit-cage feature (output: $(echo "$output2" | head -c 200))"
    fi
fi

# ---------------------------------------------------------------------------
# Assertion 3: --status closed returns RABBIT-CAGE-1 (a known closed bug)
#
# Expected behavior (post-fix): RABBIT-CAGE-1 has status=closed, must appear.
# Current behavior: reads from wrong root → empty → FAIL.
# ---------------------------------------------------------------------------
A3_LABEL="A3: --status closed output includes RABBIT-CAGE-1"

output3="$(cd "$REPO_ROOT" && bash "$SCRIPT" --status closed 2>&1)"
exit3=$?

if [ $exit3 -ne 0 ]; then
    assert_fail "$A3_LABEL" "script exited with code $exit3"
elif echo "$output3" | jq -e '[ .[] | select(.name == "RABBIT-CAGE-1") ] | length > 0' > /dev/null 2>&1; then
    assert_pass "$A3_LABEL"
else
    assert_fail "$A3_LABEL" "RABBIT-CAGE-1 not in --status closed output (output: $(echo "$output3" | head -c 200))"
fi

# ---------------------------------------------------------------------------
# Assertion 4: --text produces human-readable lines matching [RABBIT-CAGE-*]
#
# Expected behavior (post-fix): at least one line matching pattern RABBIT-CAGE-.
# Current behavior: reads from wrong root → "(no bugs)" → no matching lines → FAIL.
# ---------------------------------------------------------------------------
A4_LABEL="A4: --text output has at least one line matching RABBIT-CAGE-"

output4="$(cd "$REPO_ROOT" && bash "$SCRIPT" --text 2>&1)"
exit4=$?

if [ $exit4 -ne 0 ]; then
    assert_fail "$A4_LABEL" "script exited with code $exit4"
elif echo "$output4" | grep -q "RABBIT-CAGE-"; then
    assert_pass "$A4_LABEL"
else
    assert_fail "$A4_LABEL" "no RABBIT-CAGE- lines in --text output (output: $(echo "$output4" | head -c 200))"
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
