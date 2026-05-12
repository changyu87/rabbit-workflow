#!/usr/bin/env bash
# test-RABBIT-CAGE-BACKLOG13-claude-md-gitignore-drift.sh
# Tests for BACKLOG-13 invariants:
#   Invariant 16: CLAUDE.md is committed to the repo; NOT listed in .gitignore.
#   Invariant 17: rbt-sync-check.sh detects committed-vs-generated drift and
#                 emits a [rabbit] warning systemMessage.
#   Contract:     rbt-sync-check.sh creates CLAUDE.md on first run if absent.
#
# These tests MUST FAIL until:
#   - CLAUDE.md is removed from .gitignore and committed to git.
#   - rbt-sync-check.sh (already handles drift and first-run) is verified
#     to emit a [rabbit]-tagged systemMessage on drift.
#
# R3-compliant: no interactive constructs, PASS/FAIL per assertion, exits 1 on failure.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/rbt-sync-check.sh"
GENERATE_SCRIPT="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"
GITIGNORE="$REPO_ROOT/.gitignore"

FAILURES=0

ok() {
    echo "  PASS t_bl13_$1: $2"
}

fail_t() {
    echo "  FAIL t_bl13_$1: $2"
    FAILURES=$(( FAILURES + 1 ))
}

echo "test-RABBIT-CAGE-BACKLOG13-claude-md-gitignore-drift.sh"
echo ""

# ─── Invariant 16: CLAUDE.md not in .gitignore; committed to git ─────────────

echo "=== Invariant 16: CLAUDE.md is committed; NOT in .gitignore ==="

# t_bl13_1: .gitignore does NOT contain CLAUDE.md as an exact line
# Currently FAILS because .gitignore has "CLAUDE.md" on line 4.
if ! grep -qxF 'CLAUDE.md' "$GITIGNORE" 2>/dev/null; then
    ok 1 ".gitignore does NOT list CLAUDE.md as an exact entry"
else
    fail_t 1 ".gitignore lists CLAUDE.md — must be removed so the file can be committed"
fi

# t_bl13_2: CLAUDE.md is tracked by git (appears in git ls-files)
# Currently FAILS because CLAUDE.md is gitignored and therefore not committed.
tracked="$(git -C "$REPO_ROOT" ls-files CLAUDE.md 2>/dev/null)"
if [ -n "$tracked" ]; then
    ok 2 "CLAUDE.md is tracked by git (appears in git ls-files)"
else
    fail_t 2 "CLAUDE.md is NOT tracked by git — must be committed to the repo"
fi

# t_bl13_3: CLAUDE.md exists on disk at repo root
# This may already pass if generate-claude-md.sh or rbt-sync-check.sh ran,
# but the above two tests guard the git-committed state.
if [ -f "$REPO_ROOT/CLAUDE.md" ]; then
    ok 3 "CLAUDE.md exists on disk at repo root"
else
    fail_t 3 "CLAUDE.md does not exist on disk at repo root"
fi

echo ""

# ─── Invariant 17: rbt-sync-check.sh detects drift and emits [rabbit] warning ─

echo "=== Invariant 17: drift detection emits [rabbit] systemMessage warning ==="

# Pre-condition: rbt-sync-check.sh and generate-claude-md.sh must exist
if [ ! -f "$SYNC_CHECK" ] || [ ! -x "$SYNC_CHECK" ]; then
    fail_t 4 "rbt-sync-check.sh missing or not executable — cannot test drift detection"
    echo ""
    echo "Results: 0 passed, $FAILURES failed"
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi

if [ ! -f "$GENERATE_SCRIPT" ] || [ ! -x "$GENERATE_SCRIPT" ]; then
    fail_t 4 "generate-claude-md.sh missing or not executable — cannot test drift detection"
    echo ""
    echo "Results: 0 passed, $FAILURES failed"
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi

ok 4 "rbt-sync-check.sh and generate-claude-md.sh exist and are executable"

# Set up a temporary RABBIT_ROOT with:
#   - a valid CLAUDE.md that differs from what generate-claude-md.sh would produce
#     (simulates committed-file drift)
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

# Minimal directory structure
mkdir -p "$TMPROOT/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT/.claude/features/policy"

# Minimal policy files
printf '# Philosophy\nMachine First.\n'    > "$TMPROOT/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'             > "$TMPROOT/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'           > "$TMPROOT/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'     > "$TMPROOT/.claude/features/policy/workflow-rules.md"

# Minimal policy-header.json
python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header', 'version': '0.0.1'}))" \
    > "$TMPROOT/.claude/features/rabbit-cage/policy-header.json"

# Copy generate-claude-md.sh into temp tree
cp "$GENERATE_SCRIPT" "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

# Write a CLAUDE.md that intentionally differs from what generate-claude-md.sh produces
# (simulating a stale committed copy that has drifted from policy sources)
printf '# Rabbit Workflow — STALE OUTDATED CONTENT\nThis is old and differs from source.\n' \
    > "$TMPROOT/CLAUDE.md"

# Run rbt-sync-check.sh with drift scenario (CLAUDE.md exists but stale)
drift_output=""
drift_exit=0
drift_output="$(RABBIT_ROOT="$TMPROOT" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" \
    || drift_exit=$?

# t_bl13_5: hook exits 0 (drift detection is not a fatal error)
if [ "$drift_exit" -eq 0 ]; then
    ok 5 "rbt-sync-check.sh exits 0 when drift detected"
else
    fail_t 5 "rbt-sync-check.sh exited $drift_exit on drift (expected 0)"
fi

# t_bl13_6: hook produces JSON output (systemMessage)
json_valid=false
if echo "$drift_output" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    json_valid=true
    ok 6 "rbt-sync-check.sh emits valid JSON on drift"
else
    fail_t 6 "rbt-sync-check.sh did not emit valid JSON on drift; got: '$drift_output'"
fi

# t_bl13_7: systemMessage contains "[rabbit]" tag (invariant 17 requirement)
sys_msg_drift=""
if $json_valid; then
    sys_msg_drift="$(echo "$drift_output" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('systemMessage', ''))
except Exception:
    pass
" 2>/dev/null)"
fi

if echo "$sys_msg_drift" | grep -q '\[rabbit\]'; then
    ok 7 "systemMessage contains '[rabbit]' tag on drift"
else
    fail_t 7 "systemMessage does NOT contain '[rabbit]' tag on drift; got: '$sys_msg_drift'"
fi

# t_bl13_8: systemMessage contains drift-related term (drift|drifted|regenerated)
if echo "$sys_msg_drift" | grep -qi 'drift\|drifted\|regenerated'; then
    ok 8 "systemMessage contains drift-related term (drift/drifted/regenerated)"
else
    fail_t 8 "systemMessage missing drift-related term; got: '$sys_msg_drift'"
fi

# t_bl13_9: CLAUDE.md was regenerated (updated on disk after drift detection)
if [ -f "$TMPROOT/CLAUDE.md" ]; then
    regen_content="$(cat "$TMPROOT/CLAUDE.md")"
    if echo "$regen_content" | grep -q 'Machine First'; then
        ok 9 "CLAUDE.md was regenerated with current policy content after drift"
    else
        fail_t 9 "CLAUDE.md exists but does not contain current policy content after drift"
    fi
else
    fail_t 9 "CLAUDE.md missing after drift detection — hook should regenerate it"
fi

echo ""

# ─── Contract: first-run scenario — CLAUDE.md created when absent ─────────────

echo "=== Contract: first-run — CLAUDE.md created when absent ==="

TMPROOT2="$(mktemp -d)"
trap 'rm -rf "$TMPROOT" "$TMPROOT2"' EXIT

# Minimal directory structure for second temp root
mkdir -p "$TMPROOT2/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT2/.claude/features/policy"

printf '# Philosophy\nMachine First.\n'    > "$TMPROOT2/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'             > "$TMPROOT2/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'           > "$TMPROOT2/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'     > "$TMPROOT2/.claude/features/policy/workflow-rules.md"

python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header', 'version': '0.0.1'}))" \
    > "$TMPROOT2/.claude/features/rabbit-cage/policy-header.json"

cp "$GENERATE_SCRIPT" "$TMPROOT2/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

# Confirm CLAUDE.md is absent (first-run condition)
if [ ! -f "$TMPROOT2/CLAUDE.md" ]; then
    ok 10 "pre-condition: CLAUDE.md absent in temp workspace (first-run scenario)"
else
    fail_t 10 "pre-condition failed: CLAUDE.md already exists in temp tree"
fi

# Run rbt-sync-check.sh with absent CLAUDE.md (first-run)
first_run_output=""
first_run_exit=0
first_run_output="$(RABBIT_ROOT="$TMPROOT2" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" \
    || first_run_exit=$?

# t_bl13_11: hook exits 0 on first-run
if [ "$first_run_exit" -eq 0 ]; then
    ok 11 "rbt-sync-check.sh exits 0 on first-run (absent CLAUDE.md)"
else
    fail_t 11 "rbt-sync-check.sh exited $first_run_exit on first-run (expected 0)"
fi

# t_bl13_12: CLAUDE.md was created on first run
if [ -f "$TMPROOT2/CLAUDE.md" ]; then
    ok 12 "CLAUDE.md was created by rbt-sync-check.sh on first run"
else
    fail_t 12 "CLAUDE.md was NOT created on first run — hook must create it when absent"
fi

# t_bl13_13: created CLAUDE.md contains policy content
if [ -f "$TMPROOT2/CLAUDE.md" ] && grep -q 'Machine First' "$TMPROOT2/CLAUDE.md"; then
    ok 13 "created CLAUDE.md contains current policy content ('Machine First' present)"
else
    fail_t 13 "created CLAUDE.md does not contain current policy content"
fi

echo ""
echo "Results: $(( 13 - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
