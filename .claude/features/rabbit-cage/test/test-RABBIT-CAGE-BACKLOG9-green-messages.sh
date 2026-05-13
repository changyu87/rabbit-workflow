#!/usr/bin/env bash
# test-RABBIT-CAGE-BACKLOG9-green-messages.sh
# Tests that all systemMessage strings emitted by the three hooks are wrapped
# in ANSI deep-green color codes (\x1b[32m ... \x1b[0m).
#
# Empirical test confirmed: ANSI color codes work in Claude Code systemMessage
# output. Markdown does not. Deep green visually marks [rabbit] system messages
# as system-emitted (not user-emitted).
#
# All tests MUST FAIL against pre-change code (plain messages, no ANSI).
# They turn green only after the seven systemMessage strings are wrapped.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.sh"
SESSION_INIT="$REPO_ROOT/.claude/features/rabbit-cage/hooks/session-init.sh"
REFRESH_HOOK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/refresh.sh"

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

# Helper: assert systemMessage starts with \x1b[32m and ends with \x1b[0m
assert_green_msg() {
    local label="$1"
    local msg="$2"

    if [ -z "$msg" ]; then
        fail_t "$label — systemMessage is empty (no output emitted)"
        return
    fi

    local result
    result="$(MSG="$msg" python3 -c "
import os
msg = os.environ['MSG']
GREEN = '\x1b[32m'
RESET = '\x1b[0m'
if GREEN in msg and RESET in msg:
    print('ok')
else:
    print('missing')
" 2>/dev/null)"

    if [ "$result" = "ok" ]; then
        ok "$label — systemMessage contains ANSI deep-green wrap (\\x1b[32m … \\x1b[0m)"
    else
        fail_t "$label — systemMessage missing ANSI green codes; got: $(printf '%q' "$msg")"
    fi
}

echo "test-RABBIT-CAGE-BACKLOG9-green-messages.sh"
echo ""

# Helper: assert systemMessage contains \x1b[31m and \x1b[0m (red alert)
assert_red_msg() {
    local label="$1"
    local msg="$2"

    if [ -z "$msg" ]; then
        fail_t "$label — systemMessage is empty (no output emitted)"
        return
    fi

    local result
    result="$(MSG="$msg" python3 -c "
import os
msg = os.environ['MSG']
RED = '\x1b[31m'
RESET = '\x1b[0m'
if RED in msg and RESET in msg:
    print('ok')
else:
    print('missing')
" 2>/dev/null)"

    if [ "$result" = "ok" ]; then
        ok "$label — systemMessage contains ANSI red wrap (\\x1b[31m … \\x1b[0m)"
    else
        fail_t "$label — systemMessage missing ANSI red codes; got: $(printf '%q' "$msg")"
    fi
}

# ─── Fixture builder ─────────────────────────────────────────────────────────
build_tmproot() {
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

    echo "$tmproot"
}

# ─── Test 1: sync-check.sh FIRST-RUN case ────────────────────────────────
TMPROOT_FR="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR"' EXIT
# No CLAUDE.md → first-run branch fires
firstrun_output="$(RABBIT_ROOT="$TMPROOT_FR" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
firstrun_msg="$(printf '%s' "$firstrun_output" | extract_sys_msg)"
assert_green_msg "sync-check.sh FIRST-RUN case" "$firstrun_msg"

# ─── Test 2: sync-check.sh DRIFT case ────────────────────────────────────
TMPROOT1="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR" "$TMPROOT1"' EXIT
printf 'STALE CONTENT\n' > "$TMPROOT1/CLAUDE.md"
drift_output="$(RABBIT_ROOT="$TMPROOT1" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
drift_msg="$(printf '%s' "$drift_output" | extract_sys_msg)"
assert_red_msg "sync-check.sh DRIFT case" "$drift_msg"

# ─── Test 3: sync-check.sh SURFACE DRIFT case ────────────────────────────
TMPROOT2="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR" "$TMPROOT1" "$TMPROOT2"' EXIT
correct_claude="$(RABBIT_ROOT="$TMPROOT2" bash "$TMPROOT2/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$correct_claude" > "$TMPROOT2/CLAUDE.md"

# Install fake test-generated-surface.sh (exits 1 = surface drift detected)
mkdir -p "$TMPROOT2/.claude/features/rabbit-cage/test"
cat > "$TMPROOT2/.claude/features/rabbit-cage/test/test-generated-surface.sh" <<'FAKESURFACE'
#!/usr/bin/env bash
exit 1
FAKESURFACE
chmod +x "$TMPROOT2/.claude/features/rabbit-cage/test/test-generated-surface.sh"

# Install fake build.sh (exits 0 = build succeeds)
cat > "$TMPROOT2/.claude/features/rabbit-cage/scripts/build.sh" <<'FAKEBUILD'
#!/usr/bin/env bash
exit 0
FAKEBUILD
chmod +x "$TMPROOT2/.claude/features/rabbit-cage/scripts/build.sh"

skills_output="$(RABBIT_ROOT="$TMPROOT2" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
skills_msg="$(printf '%s' "$skills_output" | extract_sys_msg)"
assert_green_msg "sync-check.sh SURFACE DRIFT case" "$skills_msg"

# ─── Test 4: session-init.sh inline-section case ─────────────────────────
TMPROOT3="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR" "$TMPROOT1" "$TMPROOT2" "$TMPROOT3"' EXIT

cat > "$TMPROOT3/CLAUDE.md" <<'INITCLAUDEMD'
# Rabbit Workflow — test header

<!-- rabbit-policy-start: generated by generate-claude-md.sh from .claude/features/policy/ — do not edit manually -->

# Philosophy

Machine First.

<!-- rabbit-policy-end -->
INITCLAUDEMD

cat > "$TMPROOT3/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh" <<'NOSKILLS'
#!/usr/bin/env bash
exit 0
NOSKILLS
chmod +x "$TMPROOT3/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"

init_output="$(RABBIT_ROOT="$TMPROOT3" bash "$SESSION_INIT" 2>/dev/null)" || true
init_msg="$(printf '%s' "$init_output" | extract_sys_msg)"
assert_green_msg "session-init.sh inline-section case" "$init_msg"

# ─── Test 5: session-init.sh @-import fallback case ──────────────────────
TMPROOT3B="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR" "$TMPROOT1" "$TMPROOT2" "$TMPROOT3" "$TMPROOT3B"' EXIT

# CLAUDE.md with no inline policy section, but with @-imports
mkdir -p "$TMPROOT3B/policy-files"
printf '# Imported Policy\nHello.\n' > "$TMPROOT3B/policy-files/p1.md"
cat > "$TMPROOT3B/CLAUDE.md" <<INITCLAUDEMD2
# Rabbit Workflow — test header

@./policy-files/p1.md
INITCLAUDEMD2

cat > "$TMPROOT3B/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh" <<'NOSKILLS2'
#!/usr/bin/env bash
exit 0
NOSKILLS2
chmod +x "$TMPROOT3B/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"

init2_output="$(RABBIT_ROOT="$TMPROOT3B" bash "$SESSION_INIT" 2>/dev/null)" || true
init2_msg="$(printf '%s' "$init2_output" | extract_sys_msg)"
assert_green_msg "session-init.sh @-import fallback case" "$init2_msg"

# ─── Test 6: refresh.sh inline-section case ──────────────────────────────
TMPROOT4="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR" "$TMPROOT1" "$TMPROOT2" "$TMPROOT3" "$TMPROOT3B" "$TMPROOT4"' EXIT

cat > "$TMPROOT4/CLAUDE.md" <<'REFRESHCLAUDEMD'
# Rabbit Workflow — test header

<!-- rabbit-policy-start: generated by generate-claude-md.sh from .claude/features/policy/ — do not edit manually -->

# Philosophy

Machine First.

<!-- rabbit-policy-end -->
REFRESHCLAUDEMD

THRESHOLD=5
printf '%s\n' "$THRESHOLD" > "$TMPROOT4/.rabbit-prompt-counter"
refresh_output="$(RABBIT_ROOT="$TMPROOT4" RABBIT_REFRESH_EVERY="$THRESHOLD" bash "$REFRESH_HOOK" 2>/dev/null)" || true
refresh_msg="$(printf '%s' "$refresh_output" | extract_sys_msg)"
assert_green_msg "refresh.sh inline-section case" "$refresh_msg"

# ─── Test 7: refresh.sh @-import fallback case ───────────────────────────
TMPROOT4B="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR" "$TMPROOT1" "$TMPROOT2" "$TMPROOT3" "$TMPROOT3B" "$TMPROOT4" "$TMPROOT4B"' EXIT

mkdir -p "$TMPROOT4B/policy-files"
printf '# Imported Policy\nHello.\n' > "$TMPROOT4B/policy-files/p1.md"
cat > "$TMPROOT4B/CLAUDE.md" <<REFRESHCLAUDEMD2
# Rabbit Workflow — test header

@./policy-files/p1.md
REFRESHCLAUDEMD2

THRESHOLD=5
printf '%s\n' "$THRESHOLD" > "$TMPROOT4B/.rabbit-prompt-counter"
refresh2_output="$(RABBIT_ROOT="$TMPROOT4B" RABBIT_REFRESH_EVERY="$THRESHOLD" bash "$REFRESH_HOOK" 2>/dev/null)" || true
refresh2_msg="$(printf '%s' "$refresh2_output" | extract_sys_msg)"
assert_green_msg "refresh.sh @-import fallback case" "$refresh2_msg"

# ─── Test 8: sync-check.sh DRIFT case must be RED ────────────────────────
TMPROOT_DRIFT8="$(build_tmproot)"
trap 'rm -rf "$TMPROOT_FR" "$TMPROOT1" "$TMPROOT2" "$TMPROOT3" "$TMPROOT3B" "$TMPROOT4" "$TMPROOT4B" "$TMPROOT_DRIFT8"' EXIT
printf 'STALE CONTENT\n' > "$TMPROOT_DRIFT8/CLAUDE.md"
drift8_output="$(RABBIT_ROOT="$TMPROOT_DRIFT8" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
drift8_msg="$(printf '%s' "$drift8_output" | extract_sys_msg)"
assert_red_msg "sync-check.sh DRIFT case must be RED (alert)" "$drift8_msg"

echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
