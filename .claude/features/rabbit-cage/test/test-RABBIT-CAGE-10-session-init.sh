#!/usr/bin/env bash
# test-RABBIT-CAGE-10-session-init.sh
# Tests that rbt-session-init.sh exists, is executable, emits valid JSON
# with an additionalContext key containing content from at least one policy file.
#
# R3-compliant: no interactive constructs, fully automated.
#
# Fails if rbt-session-init.sh does not exist (pre-fix state).
# Passes after the hook is created and implemented.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
HOOK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/rbt-session-init.sh"

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

echo "test-RABBIT-CAGE-10-session-init.sh"

# t1: rbt-session-init.sh exists
if [ -f "$HOOK" ]; then
    ok 1 "rbt-session-init.sh exists"
else
    fail_t 1 "rbt-session-init.sh does not exist at $HOOK"
fi

# t2: rbt-session-init.sh is executable
if [ -x "$HOOK" ]; then
    ok 2 "rbt-session-init.sh is executable"
else
    fail_t 2 "rbt-session-init.sh is not executable"
fi

# t3: rbt-session-init.sh exits 0
if [ -f "$HOOK" ] && [ -x "$HOOK" ]; then
    if bash "$HOOK" > /dev/null 2>&1; then
        ok 3 "rbt-session-init.sh exits 0"
    else
        fail_t 3 "rbt-session-init.sh exited non-zero"
    fi
else
    fail_t 3 "skipped — hook missing or not executable"
fi

# t4: output is valid JSON
if [ -f "$HOOK" ] && [ -x "$HOOK" ]; then
    output=$(bash "$HOOK" 2>/dev/null)
    if echo "$output" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        ok 4 "output is valid JSON"
    else
        fail_t 4 "output is not valid JSON"
    fi
else
    fail_t 4 "skipped — hook missing or not executable"
fi

# t5: JSON has 'additionalContext' key
if [ -f "$HOOK" ] && [ -x "$HOOK" ]; then
    output=$(bash "$HOOK" 2>/dev/null)
    if echo "$output" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'additionalContext' in d else 1)" 2>/dev/null; then
        ok 5 "JSON has 'additionalContext' key"
    else
        fail_t 5 "JSON missing 'additionalContext' key"
    fi
else
    fail_t 5 "skipped — hook missing or not executable"
fi

# t6: additionalContext is non-empty and contains text from a policy file
if [ -f "$HOOK" ] && [ -x "$HOOK" ]; then
    output=$(bash "$HOOK" 2>/dev/null)
    context=$(echo "$output" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('additionalContext',''))" 2>/dev/null)
    if [ -n "$context" ] && echo "$context" | grep -q "Machine First"; then
        ok 6 "additionalContext is non-empty and contains 'Machine First' from philosophy.md"
    else
        fail_t 6 "additionalContext is empty or does not contain 'Machine First'"
    fi
else
    fail_t 6 "skipped — hook missing or not executable"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
