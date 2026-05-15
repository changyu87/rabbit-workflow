#!/usr/bin/env bash
# test-RABBIT-CAGE-BUG123.sh
# Tests for three rabbit-cage bugs:
#
# BUG-1 (RABBIT-CAGE-BUG-1): sync-check.sh SCOPE GUARD OFF alert uses Python \xNN
#   byte escapes instead of literal Unicode characters, producing garbled output.
#   Fix: use literal 🔓 and ━ characters in the Python string.
#
# BUG-2 (RABBIT-CAGE-BUG-2): No mechanism to revoke a session scope override.
#   Fix: scope-guard-on.sh script that removes .rabbit-scope-override.
#
# BUG-3 (RABBIT-CAGE-BUG-3): extract_bash_targets double-quoted region stripping
#   lacks re.DOTALL, causing false-positive DENY on multi-line --description args.
#   Fix: add re.DOTALL flag to the double-quoted re.sub call.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.py"
SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.py"
SCOPE_GUARD_ON="$REPO_ROOT/.claude/features/rabbit-cage/scripts/scope-guard-on.py"

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

# Build a minimal temp RABBIT_ROOT with a clean CLAUDE.md so drift check passes,
# and a minimal surface so sync-check.sh reaches the override alert section.
build_tmproot_clean() {
    local tmproot
    tmproot="$(mktemp -d)"
    mkdir -p "$tmproot/.claude/features/rabbit-cage/scripts"
    mkdir -p "$tmproot/.claude/features/policy"

    printf '# Philosophy\nMachine First.\n'   > "$tmproot/.claude/features/policy/philosophy.md"
    printf '# Spec Rules\nSpec.\n'            > "$tmproot/.claude/features/policy/spec-rules.md"
    printf '# Coding Rules\nCode.\n'          > "$tmproot/.claude/features/policy/coding-rules.md"

    python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
        > "$tmproot/.claude/features/rabbit-cage/policy-header.json"

    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.py" \
       "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md.py"
    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py" \
       "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py"

    python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
        > "$tmproot/.claude/features/registry.json"

    local correct_claude
    correct_claude="$(RABBIT_ROOT="$tmproot" python3 "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md.py" 2>/dev/null)"
    printf '%s\n' "$correct_claude" > "$tmproot/CLAUDE.md"

    echo "$tmproot"
}

# Call extract_bash_targets from scope-guard.py via direct module import.
# (The bash-source approach used pre-migration is no longer applicable.)
source_and_extract() {
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

echo "test-RABBIT-CAGE-BUG123.sh"
echo ""

# ============================================================================
# BUG-1: SCOPE GUARD OFF alert must emit literal 🔓 and ━ characters
# The Python string must NOT use \xNN byte escapes for these characters.
# ============================================================================
echo "=== BUG-1: SCOPE GUARD OFF alert uses literal emoji and box-drawing chars ==="

TMPROOT_BUG1="$(build_tmproot_clean)"
echo "session" > "$TMPROOT_BUG1/.rabbit-scope-override"

bug1_output=""
bug1_output="$(RABBIT_ROOT="$TMPROOT_BUG1" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
bug1_msg="$(printf '%s' "$bug1_output" | extract_sys_msg)"

# BUG-1a: message contains the literal lock emoji 🔓 (U+1F513)
# Use a temp file to avoid shell env-var multi-byte truncation issues
_bug1_tmp="$(mktemp)"
printf '%s' "$bug1_msg" > "$_bug1_tmp"
bug1_has_lock="$(python3 -c "
import sys
with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
    msg = f.read()
print('yes' if '\U0001f513' in msg else 'no')
" "$_bug1_tmp" 2>/dev/null)"
rm -f "$_bug1_tmp"

if [ "$bug1_has_lock" = "yes" ]; then
    ok "BUG-1a: SCOPE GUARD OFF message contains literal 🔓 (U+1F513)"
else
    fail_t "BUG-1a: SCOPE GUARD OFF message does NOT contain literal 🔓 — got: $(printf '%q' "$bug1_msg")"
fi

# BUG-1b: message contains the literal box-drawing char ━ (U+2501)
_bug1_tmp="$(mktemp)"
printf '%s' "$bug1_msg" > "$_bug1_tmp"
bug1_has_box="$(python3 -c "
import sys
with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
    msg = f.read()
print('yes' if '━' in msg else 'no')
" "$_bug1_tmp" 2>/dev/null)"
rm -f "$_bug1_tmp"

if [ "$bug1_has_box" = "yes" ]; then
    ok "BUG-1b: SCOPE GUARD OFF message contains literal ━ (U+2501)"
else
    fail_t "BUG-1b: SCOPE GUARD OFF message does NOT contain literal ━ — got: $(printf '%q' "$bug1_msg")"
fi

# BUG-1c: message does NOT contain garbled byte-escape artifacts like U+00F0 (ð)
# (which appear when \xf0\x9f... Python 3 byte escapes are used in a Unicode string)
_bug1_tmp="$(mktemp)"
printf '%s' "$bug1_msg" > "$_bug1_tmp"
bug1_no_garble="$(python3 -c "
import sys
with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
    msg = f.read()
# If the Python byte-escape bug is present, the string contains U+00F0 (ð)
# instead of the intended emoji (which requires bytes f0 9f 94 93 not code points)
garbled = '\xf0' in msg or '\xe2' in msg
print('yes' if garbled else 'no')
" "$_bug1_tmp" 2>/dev/null)"
rm -f "$_bug1_tmp"

if [ "$bug1_no_garble" = "no" ]; then
    ok "BUG-1c: SCOPE GUARD OFF message does NOT contain garbled byte-escape artifacts"
else
    fail_t "BUG-1c: SCOPE GUARD OFF message contains garbled byte-escape artifacts — bytes escaped as \\\\xNN in Python 3 Unicode string"
fi

rm -rf "$TMPROOT_BUG1"

echo ""

# ============================================================================
# BUG-2: scope-guard-on.sh exists and revokes .rabbit-scope-override
# ============================================================================
echo "=== BUG-2: scope-guard-on.sh exists and revokes session override ==="

# BUG-2a: script exists and is executable
if [ -x "$SCOPE_GUARD_ON" ]; then
    ok "BUG-2a: scope-guard-on.sh exists and is executable"
else
    fail_t "BUG-2a: scope-guard-on.sh does NOT exist or is not executable at $SCOPE_GUARD_ON"
fi

# BUG-2b: script removes .rabbit-scope-override when session override is active
TMPDIR_BUG2="$(mktemp -d)"
echo "session" > "$TMPDIR_BUG2/.rabbit-scope-override"

if [ -x "$SCOPE_GUARD_ON" ]; then
    RABBIT_ROOT="$TMPDIR_BUG2" python3 "$SCOPE_GUARD_ON" >/dev/null 2>&1 || true
    if [ ! -f "$TMPDIR_BUG2/.rabbit-scope-override" ]; then
        ok "BUG-2b: scope-guard-on.sh removed .rabbit-scope-override (session override revoked)"
    else
        fail_t "BUG-2b: scope-guard-on.sh did NOT remove .rabbit-scope-override"
    fi
else
    fail_t "BUG-2b: skipped (scope-guard-on.sh not executable)"
fi

# BUG-2c: script is a no-op when no override exists (exits 0, no error)
if [ -x "$SCOPE_GUARD_ON" ]; then
    RABBIT_ROOT="$TMPDIR_BUG2" python3 "$SCOPE_GUARD_ON" >/dev/null 2>&1
    noop_exit=$?
    if [ "$noop_exit" -eq 0 ]; then
        ok "BUG-2c: scope-guard-on.sh exits 0 when no override is active (no-op)"
    else
        fail_t "BUG-2c: scope-guard-on.sh exited $noop_exit when no override active — expected 0"
    fi
else
    fail_t "BUG-2c: skipped (scope-guard-on.sh not executable)"
fi

rm -rf "$TMPDIR_BUG2"

# BUG-2d: script also removes one-time override (not just session)
TMPDIR_BUG2D="$(mktemp -d)"
echo "one-time" > "$TMPDIR_BUG2D/.rabbit-scope-override"

if [ -x "$SCOPE_GUARD_ON" ]; then
    RABBIT_ROOT="$TMPDIR_BUG2D" python3 "$SCOPE_GUARD_ON" >/dev/null 2>&1 || true
    if [ ! -f "$TMPDIR_BUG2D/.rabbit-scope-override" ]; then
        ok "BUG-2d: scope-guard-on.sh removed .rabbit-scope-override (one-time override revoked)"
    else
        fail_t "BUG-2d: scope-guard-on.sh did NOT remove .rabbit-scope-override for one-time mode"
    fi
else
    fail_t "BUG-2d: skipped (scope-guard-on.sh not executable)"
fi

rm -rf "$TMPDIR_BUG2D"

echo ""

# ============================================================================
# BUG-3: extract_bash_targets must NOT false-positive on multi-line double-quoted
#   --description arguments containing -> or > patterns across continuation lines.
# ============================================================================
echo "=== BUG-3: extract_bash_targets handles multi-line double-quoted strings ==="

# BUG-3a: multi-line --description with '-> U+00F0' inside does NOT yield that as a target
# This simulates the exact pattern that caused false DENY: a Bash command with a
# backslash-newline continuation inside a double-quoted --description argument.
CMD_BUG3A='gh pr create --title "Test PR" --description "Changes: \
-> U+00F0 is the padlock emoji \
Fix garbled output"'

targets_bug3a="$(source_and_extract "$CMD_BUG3A" 2>/dev/null)"
if printf '%s' "$targets_bug3a" | grep -qF 'U+00F0' 2>/dev/null; then
    fail_t "BUG-3a: false positive — 'U+00F0' inside multi-line double-quoted string detected as write target"
elif printf '%s' "$targets_bug3a" | grep -q 'padlock\|garbled\|Changes' 2>/dev/null; then
    fail_t "BUG-3a: false positive — content inside multi-line double-quoted string detected as write target"
else
    ok "BUG-3a: multi-line double-quoted --description with '-> U+00F0' is NOT a false positive"
fi

# BUG-3b: real unquoted redirect after multi-line quoted arg IS still detected (regression guard)
CMD_BUG3B='gh pr create --description "multi \
line desc" > /tmp/real_out_bug3b'

targets_bug3b="$(source_and_extract "$CMD_BUG3B" 2>/dev/null)"
if printf '%s' "$targets_bug3b" | grep -q '/tmp/real_out_bug3b' 2>/dev/null; then
    ok "BUG-3b: real unquoted redirect after multi-line quoted arg IS detected (no regression)"
else
    fail_t "BUG-3b: regression — real unquoted redirect '/tmp/real_out_bug3b' was NOT detected"
fi

# BUG-3c: simple single-line double-quoted string still strips correctly (regression guard)
CMD_BUG3C='echo "some > /tmp/evil_bug3c here"'
targets_bug3c="$(source_and_extract "$CMD_BUG3C" 2>/dev/null)"
if printf '%s' "$targets_bug3c" | grep -q '/tmp/evil_bug3c' 2>/dev/null; then
    fail_t "BUG-3c: false positive — redirect inside single-line double-quoted string detected"
else
    ok "BUG-3c: redirect inside single-line double-quoted string is NOT a false positive (regression guard)"
fi

echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
