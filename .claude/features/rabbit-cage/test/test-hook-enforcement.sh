#!/usr/bin/env bash
# test-hook-enforcement.sh
# Tests two guarantees for hook enforcement hardening.
# R3-compliant: no interactive constructs, prints PASS/FAIL per assertion, exits 1 on any failure.
#
# GUARANTEE 1: scope-guard restricts writes to active feature directory subtree
# GUARANTEE 2: scope-guard blocks writes to a feature in test-green state

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"

SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.sh"
SETTINGS_JSON="$REPO_ROOT/.claude/features/rabbit-cage/settings.json"
FEATURE_JSON="$REPO_ROOT/.claude/features/rabbit-cage/feature.json"

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

echo "test-hook-enforcement.sh"
echo ""
echo "=== GUARANTEE 1: scope-guard restricts writes to active feature directory ==="

# t1: scope-guard.sh contains logic that reads the feature name / looks up registry.json
if grep -qE 'registry\.json|REGISTRY' "$SCOPE_GUARD" 2>/dev/null; then
    ok 1 "scope-guard.sh references registry.json for feature path lookup"
else
    fail_t 1 "scope-guard.sh does NOT reference registry.json — missing directory-restriction logic"
fi

# t2: scope-guard.sh rejects a Write to .claude/features/contract/ when scope is rabbit-cage
# Set up a temporary .rabbit-scope-active marker pointing to rabbit-cage
MARKER="$REPO_ROOT/.rabbit-scope-active"
MARKER_EXISTED=0
MARKER_BACKUP=""
if [ -f "$MARKER" ]; then
    MARKER_EXISTED=1
    MARKER_BACKUP="$(cat "$MARKER")"
fi

echo "rabbit-cage" > "$MARKER"

t2_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/contract/foo.txt"}}'
t2_exit=0
echo "$t2_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t2_exit=$?

if [ "$t2_exit" -eq 2 ]; then
    ok 2 "scope-guard exits 2 (deny) for Write to .claude/features/contract/ when scope is rabbit-cage"
else
    fail_t 2 "scope-guard exited $t2_exit (expected 2/deny) for Write outside active feature dir — directory restriction not implemented"
fi

# Restore marker
if [ "$MARKER_EXISTED" -eq 1 ]; then
    echo "$MARKER_BACKUP" > "$MARKER"
else
    rm -f "$MARKER"
fi

echo ""
echo "=== GUARANTEE 2: scope-guard blocks writes to a feature in test-green state ==="

# t3: scope-guard.sh contains logic that checks tdd_state
if grep -q 'tdd_state' "$SCOPE_GUARD" 2>/dev/null; then
    ok 3 "scope-guard.sh references tdd_state — has test-green enforcement logic"
else
    fail_t 3 "scope-guard.sh does NOT reference tdd_state — missing test-green block logic"
fi

# t4: scope-guard exits 0 for a Write to rabbit-cage when tdd_state is test-red,
#     and exits 2 when tdd_state is test-green.
#
# Setup: ensure marker points to rabbit-cage
MARKER_EXISTED=0
MARKER_BACKUP=""
if [ -f "$MARKER" ]; then
    MARKER_EXISTED=1
    MARKER_BACKUP="$(cat "$MARKER")"
fi
echo "rabbit-cage" > "$MARKER"

# Preserve original feature.json
FEATURE_JSON_BACKUP="$(cat "$FEATURE_JSON")"

# --- Part A: Write to rabbit-cage while tdd_state=test-red (should allow / exit 0) ---
python3 -c "
import json
with open('$FEATURE_JSON') as f:
    d = json.load(f)
d['tdd_state'] = 'test-red'
with open('$FEATURE_JSON', 'w') as f:
    json.dump(d, f, indent=2)
" 2>/dev/null
t4a_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t4a_exit=0
echo "$t4a_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t4a_exit=$?

# --- Part B: temporarily set tdd_state=test-green in feature.json ---
python3 -c "
import json
with open('$FEATURE_JSON') as f:
    d = json.load(f)
d['tdd_state'] = 'test-green'
with open('$FEATURE_JSON', 'w') as f:
    json.dump(d, f, indent=2)
" 2>/dev/null

t4b_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t4b_exit=0
echo "$t4b_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t4b_exit=$?

# Restore feature.json
echo "$FEATURE_JSON_BACKUP" > "$FEATURE_JSON"

# Restore marker
if [ "$MARKER_EXISTED" -eq 1 ]; then
    echo "$MARKER_BACKUP" > "$MARKER"
else
    rm -f "$MARKER"
fi

# Evaluate t4: test-red should allow (exit 0), test-green should deny (exit 2)
if [ "$t4a_exit" -eq 0 ] && [ "$t4b_exit" -eq 2 ]; then
    ok 4 "scope-guard exits 0 for test-red and exits 2 for test-green on same Write target"
elif [ "$t4a_exit" -ne 0 ]; then
    fail_t 4 "scope-guard exited $t4a_exit (expected 0) when tdd_state=test-red — allow path broken"
else
    fail_t 4 "scope-guard exited $t4b_exit (expected 2) when tdd_state=test-green — test-green block not implemented"
fi

echo ""
echo "=== CLEANUP: inert Agent hook artifacts removed ==="

# t5: settings.json PreToolUse matcher does NOT contain "Agent" (removed — inert)
if ! grep -q '"Write|Edit|Bash|Agent"' "$SETTINGS_JSON" 2>/dev/null; then
    ok 5 "PreToolUse matcher does not contain Agent (inert hook cleaned up)"
else
    fail_t 5 "PreToolUse matcher still contains Agent — inert hook not cleaned up"
fi

# t6: rbt-policy-check.sh does NOT exist (removed — inert)
POLICY_HOOK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/rbt-policy-check.sh"
if [ ! -f "$POLICY_HOOK" ]; then
    ok 6 "rbt-policy-check.sh does not exist (inert hook removed)"
else
    fail_t 6 "rbt-policy-check.sh still exists — inert hook not cleaned up"
fi

echo ""
echo "=== METADATA EXCEPTION: rabbit-feature-touch excludes bug/backlog filing ==="

SKILL_MD="$REPO_ROOT/.claude/features/rabbit-cage/skills/rabbit-feature-touch/SKILL.md"
# t7: skill description explicitly excludes metadata-only operations
if grep -qiE 'bug.filing|backlog.filing|metadata.only|not for.*bug|not for.*backlog' "$SKILL_MD" 2>/dev/null; then
    ok 7 "rabbit-feature-touch SKILL.md excludes metadata-only operations (bug/backlog filing)"
else
    fail_t 7 "rabbit-feature-touch SKILL.md does not exclude metadata-only operations — bug/backlog filing incorrectly triggers TDD"
fi

echo ""
echo "Results: $pass passed, $fail failed"

if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
