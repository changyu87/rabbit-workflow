#!/usr/bin/env bash
# test-RABBIT-CAGE-BACKLOG10-override.sh
# Tests the scope-guard override feature (RABBIT-CAGE-BACKLOG-10).
#
# Two new marker files:
#   .rabbit-scope-override  = "one-time" | "session"
#   .rabbit-scope-override-used  (existence-only flag)
#
# scope-guard.sh new allow paths:
#   session  -> ALLOW, file stays
#   one-time -> ALLOW, delete the file, create .rabbit-scope-override-used
#
# sync-check.sh Stop hook new behaviors:
#   .rabbit-scope-override = "session"  -> emit red alert
#   .rabbit-scope-override-used exists  -> emit red alert once, delete file
#
# gitignore: both files must appear in .gitignore
#
# All 10 tests MUST FAIL against current code (feature not yet implemented).
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SCOPE_GUARD="$REPO_ROOT/.claude/features/rabbit-cage/hooks/scope-guard.sh"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.sh"
GITIGNORE="$REPO_ROOT/.gitignore"

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

# Helper: build a minimal temp RABBIT_ROOT with enough structure for sync-check.sh
# to pass its normal drift check (CLAUDE.md matches generated output).
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

    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
       "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

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
    correct_claude="$(RABBIT_ROOT="$tmproot" bash "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
    printf '%s\n' "$correct_claude" > "$tmproot/CLAUDE.md"

    echo "$tmproot"
}

echo "test-RABBIT-CAGE-BACKLOG10-override.sh"
echo ""
echo "=== GITIGNORE: both override markers must be listed ==="

# t1: .rabbit-scope-override appears in .gitignore
if grep -qxF '.rabbit-scope-override' "$GITIGNORE" 2>/dev/null; then
    ok ".rabbit-scope-override is listed in .gitignore"
else
    fail_t ".rabbit-scope-override is NOT listed in .gitignore"
fi

# t2: .rabbit-scope-override-used appears in .gitignore
if grep -qxF '.rabbit-scope-override-used' "$GITIGNORE" 2>/dev/null; then
    ok ".rabbit-scope-override-used is listed in .gitignore"
else
    fail_t ".rabbit-scope-override-used is NOT listed in .gitignore"
fi

echo ""
echo "=== SCOPE-GUARD: session override ==="

# scope-guard.sh resolves REPO_ROOT via git from its own location (the real repo),
# so all target paths must be inside the real repo.
# We manipulate the real .rabbit-scope-active and real feature.json temporarily,
# following the same pattern as test-hook-enforcement.sh.
#
# Strategy: set tdd_state=test-green in real feature.json (which currently causes DENY),
# then set .rabbit-scope-override=session and confirm the override produces ALLOW.
# This ensures these tests FAIL before the override feature is implemented.

MARKER="$REPO_ROOT/.rabbit-scope-active"
FEATURE_JSON="$REPO_ROOT/.claude/features/rabbit-cage/feature.json"
OVERRIDE_MARKER="$REPO_ROOT/.rabbit-scope-override"
OVERRIDE_USED="$REPO_ROOT/.rabbit-scope-override-used"

# Preserve original state
MARKER_EXISTED=0; MARKER_BACKUP=""
if [ -f "$MARKER" ]; then MARKER_EXISTED=1; MARKER_BACKUP="$(cat "$MARKER")"; fi
FEATURE_JSON_BACKUP="$(cat "$FEATURE_JSON")"
# Clean any leftover override markers from prior runs
rm -f "$OVERRIDE_MARKER" "$OVERRIDE_USED"

# Set scope to rabbit-cage and tdd_state=test-green
echo "rabbit-cage" > "$MARKER"
python3 -c "
import json
with open('$FEATURE_JSON') as f:
    d = json.load(f)
d['tdd_state'] = 'test-green'
with open('$FEATURE_JSON', 'w') as f:
    json.dump(d, f, indent=2)
" 2>/dev/null

# Confirm without override it is DENIED (sanity / pre-condition)
t3_pre_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t3_pre_exit=0
echo "$t3_pre_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t3_pre_exit=$?

# Now place the session override
echo "session" > "$OVERRIDE_MARKER"

# t3: session override — Write to scoped dir is ALLOWED when override=session,
#     even though tdd_state=test-green (currently denies without override).
t3_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t3_exit=0
echo "$t3_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t3_exit=$?

if [ "$t3_exit" -eq 0 ] && [ "$t3_pre_exit" -eq 2 ]; then
    ok "scope-guard exits 0 (ALLOW) when .rabbit-scope-override=session (overrides test-green deny)"
elif [ "$t3_pre_exit" -ne 2 ]; then
    fail_t "pre-condition failed: scope-guard did not deny test-green write (got $t3_pre_exit, expected 2) — test setup error"
else
    fail_t "scope-guard exited $t3_exit (expected 0/ALLOW) with .rabbit-scope-override=session — override not implemented"
fi

# t4: scope-guard.sh contains logic that reads .rabbit-scope-override
#     (structural test — fails until override handling is implemented)
if grep -qE '\.rabbit-scope-override' "$SCOPE_GUARD" 2>/dev/null; then
    ok "scope-guard.sh references .rabbit-scope-override — override logic is present"
else
    fail_t "scope-guard.sh does NOT reference .rabbit-scope-override — override logic not implemented"
fi

# Clean up session override
rm -f "$OVERRIDE_MARKER"

echo ""
echo "=== SCOPE-GUARD: one-time override ==="

# Set one-time override (tdd_state still test-green, so without override it would deny)
echo "one-time" > "$OVERRIDE_MARKER"
rm -f "$OVERRIDE_USED"

t5_input='{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t5_exit=0
echo "$t5_input" | bash "$SCOPE_GUARD" > /dev/null 2>&1 || t5_exit=$?

# t5: one-time override — Write is ALLOWED (despite test-green state)
if [ "$t5_exit" -eq 0 ]; then
    ok "scope-guard exits 0 (ALLOW) when .rabbit-scope-override=one-time (overrides test-green deny)"
else
    fail_t "scope-guard exited $t5_exit (expected 0/ALLOW) with .rabbit-scope-override=one-time — override not implemented"
fi

# t6: one-time override — .rabbit-scope-override is deleted after the ALLOW
if [ ! -f "$OVERRIDE_MARKER" ]; then
    ok ".rabbit-scope-override is deleted after one-time override ALLOW"
else
    fail_t ".rabbit-scope-override still exists after one-time override — it should have been deleted"
fi

# t7: one-time override — .rabbit-scope-override-used is created after the ALLOW
if [ -f "$OVERRIDE_USED" ]; then
    ok ".rabbit-scope-override-used is created after one-time override ALLOW"
else
    fail_t ".rabbit-scope-override-used was NOT created after one-time override — used-flag not implemented"
fi

# Restore feature.json and scope marker
echo "$FEATURE_JSON_BACKUP" > "$FEATURE_JSON"
if [ "$MARKER_EXISTED" -eq 1 ]; then
    echo "$MARKER_BACKUP" > "$MARKER"
else
    rm -f "$MARKER"
fi
rm -f "$OVERRIDE_MARKER" "$OVERRIDE_USED"

echo ""
echo "=== RBT-SYNC-CHECK: override alert messages ==="

# t8: Stop hook emits red alert when .rabbit-scope-override=session
TMPROOT8="$(build_tmproot_clean)"
trap 'rm -rf "$TMPROOT8"' EXIT

echo "session" > "$TMPROOT8/.rabbit-scope-override"

t8_output=""
t8_output="$(RABBIT_ROOT="$TMPROOT8" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t8_msg="$(printf '%s' "$t8_output" | extract_sys_msg)"

# The alert must exist and contain red ANSI code \x1b[31m
t8_has_red="$(MSG="$t8_msg" python3 -c "
import os
msg = os.environ.get('MSG', '')
RED = '\x1b[31m'
RESET = '\x1b[0m'
print('yes' if RED in msg and RESET in msg else 'no')
" 2>/dev/null)"

if [ "$t8_has_red" = "yes" ]; then
    ok "sync-check.sh emits red ANSI alert when .rabbit-scope-override=session"
else
    fail_t "sync-check.sh did NOT emit red ANSI alert for session override (msg: $(printf '%q' "$t8_msg"))"
fi

# t9: Stop hook emits red alert when .rabbit-scope-override-used exists
TMPROOT9="$(build_tmproot_clean)"
trap 'rm -rf "$TMPROOT8" "$TMPROOT9"' EXIT

touch "$TMPROOT9/.rabbit-scope-override-used"

t9_output=""
t9_output="$(RABBIT_ROOT="$TMPROOT9" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t9_msg="$(printf '%s' "$t9_output" | extract_sys_msg)"

t9_has_red="$(MSG="$t9_msg" python3 -c "
import os
msg = os.environ.get('MSG', '')
RED = '\x1b[31m'
RESET = '\x1b[0m'
print('yes' if RED in msg and RESET in msg else 'no')
" 2>/dev/null)"

if [ "$t9_has_red" = "yes" ]; then
    ok "sync-check.sh emits red ANSI alert when .rabbit-scope-override-used exists"
else
    fail_t "sync-check.sh did NOT emit red ANSI alert for override-used flag (msg: $(printf '%q' "$t9_msg"))"
fi

# t10: Stop hook DELETES .rabbit-scope-override-used after emitting alert (one-shot consumption)
if [ ! -f "$TMPROOT9/.rabbit-scope-override-used" ]; then
    ok ".rabbit-scope-override-used is deleted by sync-check.sh after alert (one-shot)"
else
    fail_t ".rabbit-scope-override-used still exists after sync-check.sh ran — one-shot deletion not implemented"
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
