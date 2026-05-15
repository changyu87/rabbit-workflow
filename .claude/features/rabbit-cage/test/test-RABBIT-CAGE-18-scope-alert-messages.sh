#!/usr/bin/env bash
# test-RABBIT-CAGE-18-scope-alert-messages.sh
# Tests that sync-check.sh emits distinct messages for _alert=session vs _alert=used.
#
# Spec invariants (from spec.md Scope-Guard Override section):
#   _alert=session → "[rabbit] SCOPE GUARD OFF (session override active)"
#   _alert=used    → "[rabbit] SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed)"
#   The two messages must be different.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.py"

FAILURES=0
TOTAL=0

ok() {
    TOTAL=$(( TOTAL + 1 ))
    echo "  PASS t$TOTAL: $1"
}

fail_t() {
    TOTAL=$(( TOTAL + 1 ))
    FAILURES=$(( FAILURES + 1 ))
    echo "  FAIL t$TOTAL: $1"
}

# Helper: extract systemMessage from JSON stdout
extract_sys_msg() {
    python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('systemMessage', ''), end='')
except Exception:
    pass
" 2>/dev/null
}

# Helper: build a minimal temp RABBIT_ROOT where CLAUDE.md matches generated output
# (so the normal drift check passes and we reach the override alert section).
build_tmproot_clean() {
    local tmproot
    tmproot="$(mktemp -d)"
    mkdir -p "$tmproot/.claude/features/rabbit-cage/scripts"
    mkdir -p "$tmproot/.claude/features/policy"

    printf '# Philosophy\nMachine First.\n'   > "$tmproot/.claude/features/policy/philosophy.md"
    printf '# Spec Rules\nSpec.\n'            > "$tmproot/.claude/features/policy/spec-rules.md"
    printf '# Coding Rules\nCode.\n'          > "$tmproot/.claude/features/policy/coding-rules.md"
    printf '# Workflow Rules\nWorkflow.\n'    > "$tmproot/.claude/features/policy/workflow-rules.md"

    python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
        > "$tmproot/.claude/features/rabbit-cage/policy-header.json"

    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.py" \
       "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md.py"
    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py" \
       "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py"

    python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
        > "$tmproot/.claude/features/registry.json"

    # Stub generate-skills-dir.sh so the skills-check branch exits cleanly (no extra JSON)
    cat > "$tmproot/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh" <<'NOSKILLS'
#!/usr/bin/env bash
exit 0
NOSKILLS
    chmod +x "$tmproot/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"

    # Generate the correct CLAUDE.md so the normal drift check passes
    local correct_claude
    correct_claude="$(RABBIT_ROOT="$tmproot" python3 "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md.py" 2>/dev/null)"
    printf '%s\n' "$correct_claude" > "$tmproot/CLAUDE.md"

    echo "$tmproot"
}

TMPROOT_SESSION=""
TMPROOT_USED=""

echo "test-RABBIT-CAGE-18-scope-alert-messages.sh"
echo ""

# ---------------------------------------------------------------------------
# t1: session alert message contains "SCOPE GUARD OFF (session override active)"
# ---------------------------------------------------------------------------
echo "=== t1: _alert=session message contains 'SCOPE GUARD OFF (session override active)' ==="

TMPROOT_SESSION="$(build_tmproot_clean)"
echo "session" > "$TMPROOT_SESSION/.rabbit-scope-override"

t1_output=""
t1_output="$(RABBIT_ROOT="$TMPROOT_SESSION" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
t1_msg="$(printf '%s' "$t1_output" | extract_sys_msg)"

EXPECTED_SESSION="SCOPE GUARD OFF (session override active)"
if printf '%s' "$t1_msg" | grep -qF "$EXPECTED_SESSION" 2>/dev/null; then
    ok "session alert contains '$EXPECTED_SESSION'"
else
    fail_t "session alert does NOT contain '$EXPECTED_SESSION' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t2: used alert message contains "SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed)"
# ---------------------------------------------------------------------------
echo "=== t2: _alert=used message contains 'SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed)' ==="

TMPROOT_USED="$(build_tmproot_clean)"
touch "$TMPROOT_USED/.rabbit-scope-override-used"

t2_output=""
t2_output="$(RABBIT_ROOT="$TMPROOT_USED" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
t2_msg="$(printf '%s' "$t2_output" | extract_sys_msg)"

EXPECTED_USED="SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed)"
if printf '%s' "$t2_msg" | grep -qF "$EXPECTED_USED" 2>/dev/null; then
    ok "used alert contains '$EXPECTED_USED'"
else
    fail_t "used alert does NOT contain '$EXPECTED_USED' (actual: $(printf '%q' "$t2_msg"))"
fi

# ---------------------------------------------------------------------------
# t3: the two messages are different from each other
# ---------------------------------------------------------------------------
echo "=== t3: session and used messages are distinct ==="

if [ "$t1_msg" != "$t2_msg" ]; then
    ok "session and used alert messages are distinct"
else
    fail_t "session and used alert messages are identical — they must be distinct"
fi

# ---------------------------------------------------------------------------
# t4: session alert still carries red ANSI code (regression guard)
# ---------------------------------------------------------------------------
echo "=== t4: session alert is still red (regression guard) ==="

t4_has_red="$(MSG="$t1_msg" python3 -c "
import os
msg = os.environ.get('MSG', '')
RED = '\x1b[31m'
RESET = '\x1b[0m'
print('yes' if RED in msg and RESET in msg else 'no')
" 2>/dev/null)"

if [ "$t4_has_red" = "yes" ]; then
    ok "session alert is red (ANSI)"
else
    fail_t "session alert is NOT red — regression in color convention"
fi

# ---------------------------------------------------------------------------
# t5: used alert carries red ANSI code
# ---------------------------------------------------------------------------
echo "=== t5: used alert is red ==="

t5_has_red="$(MSG="$t2_msg" python3 -c "
import os
msg = os.environ.get('MSG', '')
RED = '\x1b[31m'
RESET = '\x1b[0m'
print('yes' if RED in msg and RESET in msg else 'no')
" 2>/dev/null)"

if [ "$t5_has_red" = "yes" ]; then
    ok "used alert is red (ANSI)"
else
    fail_t "used alert is NOT red — must use red ANSI code per spec"
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
[ -n "$TMPROOT_SESSION" ] && rm -rf "$TMPROOT_SESSION"
[ -n "$TMPROOT_USED" ] && rm -rf "$TMPROOT_USED"

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
