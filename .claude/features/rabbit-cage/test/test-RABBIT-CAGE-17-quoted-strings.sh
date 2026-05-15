#!/usr/bin/env bash
# test-RABBIT-CAGE-17-quoted-strings.sh
# Verifies extract_bash_targets() in scope-guard.py is quote-aware.
#
# After the .sh→.py migration, scope-guard.py is no longer bash-sourceable.
# We invoke scope-guard.py via its standard JSON-stdin tool-input contract
# and assert on its DENY/ALLOW exit code.
#
# Test logic: a Bash command containing a "redirect" inside a quoted string
# should NOT cause scope-guard to deny (no real write target). A command
# with a real unquoted redirect into a repo-internal path SHOULD cause deny.
#
# R3-compliant: no interactive constructs, exits 1 on any failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.py"

FAILURES=0

ok() { echo "  PASS t_rc17_$1: $2"; }
fail_t() { echo "  FAIL t_rc17_$1: $2"; FAILURES=$((FAILURES+1)); }

# Call extract_bash_targets directly by importing scope-guard.py as a module.
# This isolates extraction-correctness from runtime ALLOW/DENY decisions
# (the live decide() depends on per-repo scope markers / overrides).
extract_targets() {
    local cmd="$1"
    SCOPE_GUARD="$SCOPE_GUARD" CMD="$cmd" python3 - <<'PYEOF'
import importlib.util, os
spec = importlib.util.spec_from_file_location('sg', os.environ['SCOPE_GUARD'])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for t in m.extract_bash_targets(os.environ['CMD']):
    print(t)
PYEOF
}

echo "test-RABBIT-CAGE-17-quoted-strings.sh"
echo ""
echo "=== RABBIT-CAGE-17: extract_bash_targets strips quoted regions ==="

# t_rc17_1: redirect inside single-quoted string — must NOT yield /tmp/evil
CMD_1="python3 -c 'import json; print({\"action\": \"x > /tmp/evil\"})'"
targets_1="$(extract_targets "$CMD_1")"
if echo "$targets_1" | grep -q '/tmp/evil'; then
    fail_t 1 "false positive: '/tmp/evil' detected as write target inside single-quoted string"
else
    ok 1 "redirect inside single-quoted string is NOT detected as write target"
fi

# t_rc17_2: redirect inside double-quoted string — must NOT yield /tmp/evil
CMD_2='echo "result sending to > /tmp/evil"'
targets_2="$(extract_targets "$CMD_2")"
if echo "$targets_2" | grep -q '/tmp/evil'; then
    fail_t 2 "false positive: '/tmp/evil' detected as write target inside double-quoted string"
else
    ok 2 "redirect inside double-quoted string is NOT detected as write target"
fi

# t_rc17_3: real unquoted redirect IS detected (regression guard)
CMD_3="cat file > /tmp/real_output"
targets_3="$(extract_targets "$CMD_3")"
if echo "$targets_3" | grep -q '/tmp/real_output'; then
    ok 3 "real unquoted redirect IS detected as write target (no regression)"
else
    fail_t 3 "regression: real unquoted redirect '/tmp/real_output' was NOT detected"
fi

# t_rc17_4: heredoc body containing '>' is NOT a false positive
CMD_4="cat <<EOF
line with > in body
goes to /tmp/heredoc_target
EOF"
targets_4="$(extract_targets "$CMD_4")"
if echo "$targets_4" | grep -q '/tmp/heredoc_target'; then
    fail_t 4 "false positive: heredoc body content detected as write target"
else
    ok 4 "heredoc body with '>' is NOT detected as write target"
fi

echo ""
echo "Results: $((4 - FAILURES)) passed, $FAILURES failed"

if [ "$FAILURES" -gt 0 ]; then
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
echo "ALL TESTS PASSED"
exit 0
