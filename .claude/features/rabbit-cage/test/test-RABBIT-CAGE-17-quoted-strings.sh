#!/usr/bin/env bash
# test-RABBIT-CAGE-17-quoted-strings.sh
# Verifies that extract_bash_targets() does not produce false positives when
# redirect-like patterns appear inside single-quoted or double-quoted strings,
# or inside heredoc bodies.
#
# R3-compliant: no interactive constructs, PASS/FAIL per assertion, exits 1 on failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.sh"

pass=0
fail=0

ok() {
    echo "  PASS t_rc17_$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t_rc17_$1: $2"
    fail=$((fail + 1))
}

echo "test-RABBIT-CAGE-17-quoted-strings.sh"
echo ""
echo "=== RABBIT-CAGE-17: extract_bash_targets strips quoted regions ==="

# Helper: run extract_bash_targets via scope-guard's Bash path.
# We construct a fake Bash tool_input JSON and capture what scope-guard
# would evaluate as targets, by temporarily setting up a scope in which
# /tmp/evil is inside the repo (impossible) — instead we just test directly
# by sourcing the function and calling it.
#
# Simpler approach: source scope-guard.sh in a subshell, override `decide`
# to echo the target instead of deciding, and confirm /tmp/evil is or is not emitted.

extract_targets() {
    local cmd="$1"
    bash -c "
source '$SCOPE_GUARD' 2>/dev/null || true
# Re-source just to get the function definition; suppress main logic
$(grep -n 'extract_bash_targets' '$SCOPE_GUARD' | head -1)
" 2>/dev/null || true

    # Simpler: extract the function body and eval it in a subshell
    bash <<'SUBSHELL'
SCOPE_GUARD_FILE='PLACEHOLDER'
SUBSHELL
}

# Direct extraction approach: source the function definition only
source_and_extract() {
    local cmd="$1"
    # Extract just the function from scope-guard.sh and evaluate it
    bash -c "
$(sed -n '/^extract_bash_targets/,/^}/p' "$SCOPE_GUARD")
extract_bash_targets $(printf '%q' "$cmd")
"
}

# t_rc17_1: redirect inside single-quoted string — must NOT emit /tmp/evil as target
# Command: python3 -c 'import json; print({"action": "x > /tmp/evil"})'
CMD_1="python3 -c 'import json; print({\"action\": \"x > /tmp/evil\"})'"
targets_1="$(source_and_extract "$CMD_1" 2>/dev/null)"
if echo "$targets_1" | grep -q '/tmp/evil'; then
    fail_t 1 "false positive: '/tmp/evil' detected as write target inside single-quoted string"
else
    ok 1 "redirect inside single-quoted string is NOT detected as write target"
fi

# t_rc17_2: redirect inside double-quoted string — must NOT emit /tmp/evil as target
# Command: echo "result -> sending to /dev/null and > /tmp/evil"
CMD_2='echo "result sending to > /tmp/evil"'
targets_2="$(source_and_extract "$CMD_2" 2>/dev/null)"
if echo "$targets_2" | grep -q '/tmp/evil'; then
    fail_t 2 "false positive: '/tmp/evil' detected as write target inside double-quoted string"
else
    ok 2 "redirect inside double-quoted string is NOT detected as write target"
fi

# t_rc17_3: real unquoted redirect IS still detected — regression guard
# Command: cat file > /tmp/real_output
CMD_3="cat file > /tmp/real_output"
targets_3="$(source_and_extract "$CMD_3" 2>/dev/null)"
if echo "$targets_3" | grep -q '/tmp/real_output'; then
    ok 3 "real unquoted redirect IS detected as write target (no regression)"
else
    fail_t 3 "regression: real unquoted redirect '/tmp/real_output' was NOT detected"
fi

# t_rc17_4: heredoc body with arrow-like text is not a false positive
# The heredoc body "some text -> in-progress" should not yield a target
CMD_4="python3 - << 'PYEOF'
some text > in-progress
PYEOF"
targets_4="$(source_and_extract "$CMD_4" 2>/dev/null)"
if echo "$targets_4" | grep -q 'in-progress'; then
    fail_t 4 "false positive: 'in-progress' detected as write target inside heredoc body"
else
    ok 4 "heredoc body with '>' is NOT detected as write target"
fi

echo ""
echo "Results: $pass passed, $fail failed"

if [ "$fail" -gt 0 ]; then
    exit 1
fi
exit 0
