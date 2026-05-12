#!/usr/bin/env bash
# test-RABBIT-CAGE-BACKLOG7-visual-messages.sh
# Tests that all three hooks emit system messages with BOTH emoji characters
# AND box-drawing border characters (━━━ or similar) for visual distinction.
#
# Feature (RABBIT-CAGE-BACKLOG-7): Make [rabbit] system messages visually
# outstanding. All three hooks should emit system messages with emoji characters
# (⚠️, ✅, 🔄, or similar) AND box-drawing border characters (━━━ or similar).
#
# All tests MUST FAIL against the current code (which has plain-text messages).
# They turn green only after the hooks are updated to emit visually rich messages.
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
    print(d.get('systemMessage', ''))
except Exception:
    pass
" 2>/dev/null
}

# Helper: assert systemMessage contains both emoji and box-drawing chars
assert_visual_msg() {
    local label="$1"
    local msg="$2"

    if [ -z "$msg" ]; then
        fail_t "$label — systemMessage is empty (no output emitted)"
        return
    fi

    # Check for any emoji: use python3 unicode category check (category starts with 'S' for symbols,
    # or check for specific ranges). We test for presence of at least one multibyte character
    # above U+1F000 (emoji block) or common emoji markers.
    has_emoji="$(python3 -c "
import sys
msg = $(python3 -c "import sys,json; print(json.dumps(sys.argv[1]))" "$msg")
found = any(ord(c) > 0x2600 for c in msg)
print('yes' if found else 'no')
" 2>/dev/null)"

    # Check for box-drawing character ━ (U+2501) or ─ (U+2500) or similar border chars
    has_border="$(python3 -c "
import sys
msg = $(python3 -c "import sys,json; print(json.dumps(sys.argv[1]))" "$msg")
border_chars = set('━─═╔╗╚╝║╠╣╦╩╬┌┐└┘│├┤┬┴┼')
found = any(c in border_chars for c in msg)
print('yes' if found else 'no')
" 2>/dev/null)"

    if [ "$has_emoji" = "yes" ] && [ "$has_border" = "yes" ]; then
        ok "$label — systemMessage contains emoji AND box-drawing border chars"
    elif [ "$has_emoji" != "yes" ] && [ "$has_border" != "yes" ]; then
        fail_t "$label — systemMessage has NEITHER emoji NOR border chars; got: '$msg'"
    elif [ "$has_emoji" != "yes" ]; then
        fail_t "$label — systemMessage has border chars but NO emoji; got: '$msg'"
    else
        fail_t "$label — systemMessage has emoji but NO border chars; got: '$msg'"
    fi
}

echo "test-RABBIT-CAGE-BACKLOG7-visual-messages.sh"
echo ""

# ─── Fixture builder ─────────────────────────────────────────────────────────
# Creates a minimal temp RABBIT_ROOT with generate-claude-md.sh infrastructure.
# Returns the temp dir path via stdout.
build_tmproot() {
    local tmproot
    tmproot="$(mktemp -d)"
    mkdir -p "$tmproot/.claude/features/rabbit-cage/scripts"
    mkdir -p "$tmproot/.claude/features/rabbit-cage"
    mkdir -p "$tmproot/.claude/features/policy"

    # Minimal policy files
    printf '# Philosophy\nMachine First.\n'   > "$tmproot/.claude/features/policy/philosophy.md"
    printf '# Spec Rules\nSpec.\n'            > "$tmproot/.claude/features/policy/spec-rules.md"
    printf '# Coding Rules\nCode.\n'          > "$tmproot/.claude/features/policy/coding-rules.md"
    printf '# Workflow Rules\nWorkflow.\n'    > "$tmproot/.claude/features/policy/workflow-rules.md"

    # policy-header.json
    python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
        > "$tmproot/.claude/features/rabbit-cage/policy-header.json"

    # Copy generate-claude-md.sh so sync-check.sh can invoke it
    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
       "$tmproot/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

    # Minimal registry.json (needed by generate-skills-dir.sh --check, which may be called)
    python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
        > "$tmproot/.claude/features/registry.json"

    echo "$tmproot"
}

# ─── Test group 1: sync-check.sh DRIFT case ──────────────────────────────
# CLAUDE.md exists but content differs from generated → drift branch fires.
TMPROOT1="$(build_tmproot)"
trap 'rm -rf "$TMPROOT1"' EXIT

# Write a CLAUDE.md with stale content to force drift detection
printf 'STALE CONTENT\n' > "$TMPROOT1/CLAUDE.md"

drift_output=""
drift_output="$(RABBIT_ROOT="$TMPROOT1" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
drift_msg="$(echo "$drift_output" | extract_sys_msg)"

assert_visual_msg "sync-check.sh DRIFT case" "$drift_msg"

# ─── Test group 2: sync-check.sh SKILLS UPDATE case ──────────────────────
# CLAUDE.md is up-to-date (no drift) but skills need updating → skills branch fires.
TMPROOT2="$(build_tmproot)"
trap 'rm -rf "$TMPROOT1" "$TMPROOT2"' EXIT

# Generate a correct CLAUDE.md so the drift branch is NOT taken
correct_claude="$(RABBIT_ROOT="$TMPROOT2" bash "$TMPROOT2/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$correct_claude" > "$TMPROOT2/CLAUDE.md"

# Install generate-skills-dir.sh so the skills-check code path can be exercised.
# We provide a version that always exits 1 from --check (simulating drift) and
# exits 0 from the update call — without touching any real skills directory.
cat > "$TMPROOT2/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh" <<'FAKESKILLS'
#!/usr/bin/env bash
# Fake generate-skills-dir.sh: --check always reports drift (exit 1)
if [[ "$*" == *"--check"* ]]; then
    exit 1
fi
exit 0
FAKESKILLS
chmod +x "$TMPROOT2/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"

skills_output=""
skills_output="$(RABBIT_ROOT="$TMPROOT2" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
skills_msg="$(echo "$skills_output" | extract_sys_msg)"

assert_visual_msg "sync-check.sh SKILLS UPDATE case" "$skills_msg"

# ─── Test group 3: session-init.sh session-start message ─────────────────
# CLAUDE.md contains an inline policy section → session-init emits additionalContext.
TMPROOT3="$(build_tmproot)"
trap 'rm -rf "$TMPROOT1" "$TMPROOT2" "$TMPROOT3"' EXIT

# Write a CLAUDE.md with inline policy (rabbit-policy-start/end)
cat > "$TMPROOT3/CLAUDE.md" <<'INITCLAUDEMD'
# Rabbit Workflow — test header

<!-- rabbit-policy-start: generated by generate-claude-md.sh from .claude/features/policy/ — do not edit manually -->

# Philosophy

Machine First. Every state, metadata, interface, and artifact is designed for
machine consumption first.

# Coding Rules

Simplicity First. Minimum code that solves the problem. Nothing speculative.

<!-- rabbit-policy-end -->
INITCLAUDEMD

# Disable generate-skills-dir.sh in this tree (no real skills to generate)
mkdir -p "$TMPROOT3/.claude/features/rabbit-cage/scripts"
cat > "$TMPROOT3/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh" <<'NOSKILLS'
#!/usr/bin/env bash
exit 0
NOSKILLS
chmod +x "$TMPROOT3/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"

init_output=""
init_output="$(RABBIT_ROOT="$TMPROOT3" bash "$SESSION_INIT" 2>/dev/null)" || true
init_msg="$(echo "$init_output" | extract_sys_msg)"

assert_visual_msg "session-init.sh session-start injection" "$init_msg"

# ─── Test group 4: refresh.sh periodic refresh message ───────────────────
# CLAUDE.md with inline policy, counter at threshold → refresh fires.
TMPROOT4="$(build_tmproot)"
trap 'rm -rf "$TMPROOT1" "$TMPROOT2" "$TMPROOT3" "$TMPROOT4"' EXIT

cat > "$TMPROOT4/CLAUDE.md" <<'REFRESHCLAUDEMD'
# Rabbit Workflow — test header

<!-- rabbit-policy-start: generated by generate-claude-md.sh from .claude/features/policy/ — do not edit manually -->

# Philosophy

Machine First. Every state, metadata, interface, and artifact is designed for
machine consumption first.

# Coding Rules

Simplicity First.

<!-- rabbit-policy-end -->
REFRESHCLAUDEMD

# Seed counter at threshold so refresh fires immediately
THRESHOLD=5
printf '%s\n' "$THRESHOLD" > "$TMPROOT4/.rbt-prompt-counter"

refresh_output=""
refresh_output="$(RABBIT_ROOT="$TMPROOT4" RBT_REFRESH_EVERY="$THRESHOLD" bash "$REFRESH_HOOK" 2>/dev/null)" || true
refresh_msg="$(echo "$refresh_output" | extract_sys_msg)"

assert_visual_msg "refresh.sh periodic refresh" "$refresh_msg"

echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
