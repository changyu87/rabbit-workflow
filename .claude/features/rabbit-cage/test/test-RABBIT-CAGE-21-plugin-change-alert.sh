#!/usr/bin/env bash
# test-RABBIT-CAGE-21-plugin-change-alert.sh
# Tests that sync-check.sh detects session plugin changes via git diff and
# emits a green [rabbit] systemMessage instructing /reload-plugins.
#
# Spec invariant 24 (updated): On every Stop, after existing drift checks,
# sync-check.sh:
# (a) Computes BASE = git merge-base HEAD main (fallback origin/main).
# (b) Runs git diff --name-only "$BASE" HEAD -- .claude/skills/ .claude/commands/ .claude/agents/
# (c) If any files changed: emits green [rabbit] systemMessage containing
#     '[rabbit]' and 'reload-plugins'.
# (d) If no files changed: silent (no output / no reload-plugins message).
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.sh"

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

# Build a minimal temp git repo with CLAUDE.md matching generated output,
# surface check stubbed out, and no override markers.
# Returns path via stdout.
make_clean_repo_with_main() {
    local d
    d="$(mktemp -d)"
    git init -q "$d"
    git -C "$d" config user.email "test@test.com"
    git -C "$d" config user.name "Test"
    git -C "$d" checkout -q -b main 2>/dev/null || true

    # Minimal directory structure for sync-check.sh
    mkdir -p "$d/.claude/features/rabbit-cage/scripts"
    mkdir -p "$d/.claude/features/policy"
    mkdir -p "$d/.claude/skills/test-skill"

    printf '# Philosophy\nMachine First.\n'   > "$d/.claude/features/policy/philosophy.md"
    printf '# Spec Rules\nSpec.\n'            > "$d/.claude/features/policy/spec-rules.md"
    printf '# Coding Rules\nCode.\n'          > "$d/.claude/features/policy/coding-rules.md"
    printf '# Workflow Rules\nWorkflow.\n'    > "$d/.claude/features/policy/workflow-rules.md"

    python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
        > "$d/.claude/features/rabbit-cage/policy-header.json"

    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
       "$d/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

    python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
        > "$d/.claude/features/registry.json"

    # Generate a clean CLAUDE.md so the drift check passes
    local correct_claude
    correct_claude="$(RABBIT_ROOT="$d" bash "$d/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
    printf '%s\n' "$correct_claude" > "$d/CLAUDE.md"

    # Commit everything to main
    git -C "$d" add -A
    git -C "$d" commit -q -m "init on main"

    echo "$d"
}

echo "test-RABBIT-CAGE-21-plugin-change-alert.sh"
echo ""

TMPROOT=""

# ---------------------------------------------------------------------------
# t1: When skills file changed since branch-point, emits systemMessage
#     containing '[rabbit]' and 'reload-plugins'
# ---------------------------------------------------------------------------
echo "=== t1: skills changed since branch-point → [rabbit] reload-plugins alert ==="

TMPROOT="$(make_clean_repo_with_main)"
trap 'rm -rf "$TMPROOT"' EXIT

# Create a session branch off main
git -C "$TMPROOT" checkout -q -b session/test-branch 2>/dev/null

# Add a change to .claude/skills/ on the session branch
mkdir -p "$TMPROOT/.claude/skills/test-skill"
printf '# Updated skill\n' > "$TMPROOT/.claude/skills/test-skill/SKILL.md"

# Regenerate CLAUDE.md so drift check passes
correct="$(RABBIT_ROOT="$TMPROOT" bash "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$correct" > "$TMPROOT/CLAUDE.md"

git -C "$TMPROOT" add -A
git -C "$TMPROOT" commit -q -m "update skills on session branch"

t1_output=""
t1_output="$(RABBIT_ROOT="$TMPROOT" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t1_msg="$(printf '%s' "$t1_output" | extract_sys_msg)"

if printf '%s' "$t1_msg" | grep -q '\[rabbit\]' 2>/dev/null; then
    ok "systemMessage contains '[rabbit]'"
else
    fail_t "systemMessage does NOT contain '[rabbit]' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t2: The message instructs the user to run /reload-plugins
# ---------------------------------------------------------------------------
echo "=== t2: plugin-change alert contains 'reload-plugins' ==="

if printf '%s' "$t1_msg" | grep -q 'reload-plugins' 2>/dev/null; then
    ok "systemMessage contains 'reload-plugins'"
else
    fail_t "systemMessage does NOT contain 'reload-plugins' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t3: The message is green (info convention, not red)
# ---------------------------------------------------------------------------
echo "=== t3: plugin-change alert is green (spec invariant 18) ==="

t3_has_green="$(MSG="$t1_msg" python3 -c "
import os
msg = os.environ.get('MSG', '')
GREEN = '\x1b[32m'
RESET = '\x1b[0m'
print('yes' if GREEN in msg and RESET in msg else 'no')
" 2>/dev/null)"

if [ "$t3_has_green" = "yes" ]; then
    ok "plugin-change alert is green (ANSI)"
else
    fail_t "plugin-change alert is NOT green — must use \x1b[32m per spec invariant 18 (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t4: The changed files are listed in the message
# ---------------------------------------------------------------------------
echo "=== t4: changed skill file is listed in the message ==="

if printf '%s' "$t1_msg" | grep -q 'SKILL.md\|test-skill\|skills' 2>/dev/null; then
    ok "message references the changed skill file/directory"
else
    fail_t "message does NOT reference changed files (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t5: When no plugin files changed since branch-point, no reload-plugins message
# ---------------------------------------------------------------------------
echo "=== t5: no skills changed since branch-point → no reload-plugins message ==="

TMPROOT2="$(make_clean_repo_with_main)"
trap 'rm -rf "$TMPROOT" "$TMPROOT2"' EXIT

# Create a session branch off main but change only a non-plugin file
git -C "$TMPROOT2" checkout -q -b session/test-no-plugin-change 2>/dev/null
printf '# Some non-plugin change\n' > "$TMPROOT2/some-non-plugin-file.txt"

# Keep CLAUDE.md matching (regenerate)
correct2="$(RABBIT_ROOT="$TMPROOT2" bash "$TMPROOT2/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$correct2" > "$TMPROOT2/CLAUDE.md"

git -C "$TMPROOT2" add -A
git -C "$TMPROOT2" commit -q -m "non-plugin change on session branch"

t5_output=""
t5_output="$(RABBIT_ROOT="$TMPROOT2" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t5_msg="$(printf '%s' "$t5_output" | extract_sys_msg)"

if printf '%s' "$t5_msg" | grep -q 'reload-plugins' 2>/dev/null; then
    fail_t "reload-plugins message emitted when no plugin files changed (false positive)"
else
    ok "no reload-plugins message when no plugin files changed"
fi

# ---------------------------------------------------------------------------
# t6: Single-JSON-per-invocation invariant — output is valid JSON or empty
# ---------------------------------------------------------------------------
echo "=== t6: sync-check.sh emits at most one JSON object (single-JSON invariant) ==="

t6_json_count="$(printf '%s' "$t1_output" | python3 -c "
import sys, json
data = sys.stdin.read().strip()
if not data:
    print(0)
else:
    # Try to parse as one JSON object
    try:
        json.loads(data)
        print(1)
    except Exception:
        # Count the number of JSON objects by trying to decode sequentially
        decoder = json.JSONDecoder()
        idx = 0
        count = 0
        while idx < len(data):
            data_slice = data[idx:].lstrip()
            if not data_slice:
                break
            try:
                obj, end = decoder.raw_decode(data_slice)
                count += 1
                idx += len(data) - len(data_slice) + end
            except:
                break
        print(count)
" 2>/dev/null)"

if [ "$t6_json_count" = "1" ]; then
    ok "exactly one JSON object emitted"
elif [ "$t6_json_count" = "0" ]; then
    # t1 should have produced output, so 0 is actually a t1 failure already captured
    ok "no JSON emitted (already caught in t1/t2)"
else
    fail_t "more than one JSON object emitted (count=$t6_json_count) — violates single-JSON-per-invocation invariant"
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
rm -rf "$TMPROOT" "$TMPROOT2" 2>/dev/null || true
trap - EXIT

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
