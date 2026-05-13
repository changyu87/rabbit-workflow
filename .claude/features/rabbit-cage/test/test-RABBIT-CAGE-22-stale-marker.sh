#!/usr/bin/env bash
# test-RABBIT-CAGE-22-stale-marker.sh
# Tests for RABBIT-CAGE-22: .rabbit-plugins-stale marker model.
#
# Spec invariant 24 (updated): plugin-change alert uses .rabbit-plugins-stale marker:
# (a) sync-check.sh emits /rabbit-refresh alert when marker exists
# (b) sync-check.sh is silent when marker is absent
# (c) build.sh writes .rabbit-plugins-stale when copying skill/command/agent targets
# (d) rabbit-refresh.md contains rm -f .rabbit-plugins-stale
# (e) session-init.sh removes .rabbit-plugins-stale at session start
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.sh"
SESSION_INIT="$REPO_ROOT/.claude/features/rabbit-cage/hooks/session-init.sh"
BUILD_SH="$REPO_ROOT/.claude/features/rabbit-cage/scripts/build.sh"
RABBIT_REFRESH_MD="$REPO_ROOT/.claude/features/rabbit-cage/commands/rabbit-refresh.md"

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

# Build a minimal temp git repo with clean CLAUDE.md and no drift conditions.
make_clean_repo() {
    local d
    d="$(mktemp -d)"
    git init -q "$d"
    git -C "$d" config user.email "test@test.com"
    git -C "$d" config user.name "Test"
    git -C "$d" checkout -q -b main 2>/dev/null || true

    mkdir -p "$d/.claude/features/rabbit-cage/scripts"
    mkdir -p "$d/.claude/features/policy"

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

    local correct
    correct="$(RABBIT_ROOT="$d" bash "$d/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
    printf '%s\n' "$correct" > "$d/CLAUDE.md"

    git -C "$d" add -A
    git -C "$d" commit -q -m "init"

    echo "$d"
}

echo "test-RABBIT-CAGE-22-stale-marker.sh"
echo ""

TMPROOT=""
TMPROOT2=""
TMPROOT3=""

# ---------------------------------------------------------------------------
# t1: When .rabbit-plugins-stale exists, sync-check.sh emits /rabbit-refresh alert
# ---------------------------------------------------------------------------
echo "=== t1: .rabbit-plugins-stale exists → sync-check emits /rabbit-refresh alert ==="

TMPROOT="$(make_clean_repo)"
trap 'rm -rf "$TMPROOT" "$TMPROOT2" "$TMPROOT3"' EXIT

# Create the stale marker
touch "$TMPROOT/.rabbit-plugins-stale"

t1_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t1_msg="$(printf '%s' "$t1_output" | extract_sys_msg)"

if printf '%s' "$t1_msg" | grep -q '\[rabbit\]' 2>/dev/null; then
    ok "systemMessage contains '[rabbit]'"
else
    fail_t "systemMessage does NOT contain '[rabbit]' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t2: Alert instructs /rabbit-refresh (not /reload-plugins)
# ---------------------------------------------------------------------------
echo "=== t2: alert instructs /rabbit-refresh ==="

if printf '%s' "$t1_msg" | grep -q 'rabbit-refresh' 2>/dev/null; then
    ok "systemMessage contains 'rabbit-refresh'"
else
    fail_t "systemMessage does NOT contain 'rabbit-refresh' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t3: Alert does NOT mention /reload-plugins (old command removed)
# ---------------------------------------------------------------------------
echo "=== t3: alert does NOT mention /reload-plugins ==="

if printf '%s' "$t1_msg" | grep -q 'reload-plugins' 2>/dev/null; then
    fail_t "systemMessage still references 'reload-plugins' — must be /rabbit-refresh (actual: $(printf '%q' "$t1_msg"))"
else
    ok "alert correctly omits 'reload-plugins'"
fi

# ---------------------------------------------------------------------------
# t4: Alert is green (invariant 18)
# ---------------------------------------------------------------------------
echo "=== t4: alert is green (ANSI invariant 18) ==="

t4_green="$(MSG="$t1_msg" python3 -c "
import os
msg = os.environ.get('MSG', '')
GREEN = '\x1b[32m'
RESET = '\x1b[0m'
print('yes' if GREEN in msg and RESET in msg else 'no')
" 2>/dev/null)"

if [ "$t4_green" = "yes" ]; then
    ok "alert is green (ANSI)"
else
    fail_t "alert is NOT green (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t5: When .rabbit-plugins-stale absent, no alert fires
# ---------------------------------------------------------------------------
echo "=== t5: .rabbit-plugins-stale absent → no alert fires ==="

TMPROOT2="$(make_clean_repo)"

# Ensure marker is NOT present
rm -f "$TMPROOT2/.rabbit-plugins-stale"

t5_output="$(RABBIT_ROOT="$TMPROOT2" RABBIT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t5_msg="$(printf '%s' "$t5_output" | extract_sys_msg)"

if printf '%s' "$t5_msg" | grep -q 'rabbit-refresh\|reload-plugins\|Plugins updated' 2>/dev/null; then
    fail_t "plugin alert fired when .rabbit-plugins-stale was absent (false positive)"
else
    ok "no plugin alert when .rabbit-plugins-stale is absent"
fi

# ---------------------------------------------------------------------------
# t6: build.sh writes .rabbit-plugins-stale when copying skill/command/agent targets
# ---------------------------------------------------------------------------
echo "=== t6: build.sh writes .rabbit-plugins-stale when copying skill/command/agent targets ==="

TMPROOT3="$(make_clean_repo)"

# Create a minimal build-contract.json with a skills target
mkdir -p "$TMPROOT3/.claude/features/contract"
mkdir -p "$TMPROOT3/.claude/features/rabbit-cage/hooks"
mkdir -p "$TMPROOT3/.claude/features/rabbit-cage/commands"
mkdir -p "$TMPROOT3/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT3/.claude/features/test-skill/skills/test-skill"

# Copy the generate-claude-md script
cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
   "$TMPROOT3/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

printf '# Test skill\n' > "$TMPROOT3/.claude/features/test-skill/skills/test-skill/SKILL.md"

python3 -c "
import json
contract = {
    'schema_version': '1.0.0',
    'owner': 'test',
    'deprecation_criterion': 'test',
    'updated': '2026-01-01',
    'targets': [
        {
            'name': 'skills/test-skill/SKILL.md',
            'type': 'copy-file',
            'source': '.claude/features/test-skill/skills/test-skill/SKILL.md',
            'destination': '.claude/skills/test-skill/SKILL.md'
        }
    ]
}
print(json.dumps(contract, indent=2))
" > "$TMPROOT3/.claude/features/contract/build-contract.json"

# Remove any stale marker before running build
rm -f "$TMPROOT3/.rabbit-plugins-stale"

bash "$BUILD_SH" "$TMPROOT3" >/dev/null 2>&1 || true

if [ -f "$TMPROOT3/.rabbit-plugins-stale" ]; then
    ok "build.sh wrote .rabbit-plugins-stale after copying a skills target"
else
    fail_t "build.sh did NOT write .rabbit-plugins-stale after copying a skills target"
fi

# ---------------------------------------------------------------------------
# t7: build.sh writes .rabbit-plugins-stale for commands targets too
# ---------------------------------------------------------------------------
echo "=== t7: build.sh writes .rabbit-plugins-stale for commands targets ==="

# Reuse TMPROOT3 but update contract to a commands target
printf '# Test command\n' > "$TMPROOT3/.claude/features/rabbit-cage/commands/test-cmd.md"

python3 -c "
import json
contract = {
    'schema_version': '1.0.0',
    'owner': 'test',
    'deprecation_criterion': 'test',
    'updated': '2026-01-01',
    'targets': [
        {
            'name': 'commands/test-cmd.md',
            'type': 'copy-file',
            'source': '.claude/features/rabbit-cage/commands/test-cmd.md',
            'destination': '.claude/commands/test-cmd.md'
        }
    ]
}
print(json.dumps(contract, indent=2))
" > "$TMPROOT3/.claude/features/contract/build-contract.json"

rm -f "$TMPROOT3/.rabbit-plugins-stale"

bash "$BUILD_SH" "$TMPROOT3" >/dev/null 2>&1 || true

if [ -f "$TMPROOT3/.rabbit-plugins-stale" ]; then
    ok "build.sh wrote .rabbit-plugins-stale after copying a commands target"
else
    fail_t "build.sh did NOT write .rabbit-plugins-stale after copying a commands target"
fi

# ---------------------------------------------------------------------------
# t8: build.sh does NOT write .rabbit-plugins-stale for non-plugin copy-file targets
# ---------------------------------------------------------------------------
echo "=== t8: build.sh does NOT write .rabbit-plugins-stale for non-plugin copy-file targets ==="

printf '# README\n' > "$TMPROOT3/source-readme.md"

python3 -c "
import json
contract = {
    'schema_version': '1.0.0',
    'owner': 'test',
    'deprecation_criterion': 'test',
    'updated': '2026-01-01',
    'targets': [
        {
            'name': 'README.md',
            'type': 'copy-file',
            'source': 'source-readme.md',
            'destination': 'README.md'
        }
    ]
}
print(json.dumps(contract, indent=2))
" > "$TMPROOT3/.claude/features/contract/build-contract.json"

rm -f "$TMPROOT3/.rabbit-plugins-stale"

bash "$BUILD_SH" "$TMPROOT3" >/dev/null 2>&1 || true

if [ -f "$TMPROOT3/.rabbit-plugins-stale" ]; then
    fail_t "build.sh incorrectly wrote .rabbit-plugins-stale for a non-plugin copy-file target"
else
    ok "build.sh did NOT write .rabbit-plugins-stale for a non-plugin target"
fi

# ---------------------------------------------------------------------------
# t9: rabbit-refresh.md contains rm -f .rabbit-plugins-stale
# ---------------------------------------------------------------------------
echo "=== t9: rabbit-refresh.md contains 'rm -f .rabbit-plugins-stale' ==="

if grep -q 'rm -f .*\.rabbit-plugins-stale' "$RABBIT_REFRESH_MD" 2>/dev/null; then
    ok "rabbit-refresh.md contains rm -f .rabbit-plugins-stale"
else
    fail_t "rabbit-refresh.md does NOT contain 'rm -f .rabbit-plugins-stale'"
fi

# ---------------------------------------------------------------------------
# t10: session-init.sh removes .rabbit-plugins-stale at session start
# ---------------------------------------------------------------------------
echo "=== t10: session-init.sh removes .rabbit-plugins-stale at session start ==="

TMPROOT_SI="$(make_clean_repo)"

# Create stale marker
touch "$TMPROOT_SI/.rabbit-plugins-stale"

# Run session-init.sh (suppress all output including git branch/checkout operations)
RABBIT_ROOT="$TMPROOT_SI" bash "$SESSION_INIT" >/dev/null 2>&1 || true

if [ -f "$TMPROOT_SI/.rabbit-plugins-stale" ]; then
    fail_t "session-init.sh did NOT remove .rabbit-plugins-stale"
else
    ok "session-init.sh removed .rabbit-plugins-stale"
fi

rm -rf "$TMPROOT_SI"

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
rm -rf "$TMPROOT" "$TMPROOT2" "$TMPROOT3" 2>/dev/null || true
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
