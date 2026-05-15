#!/usr/bin/env bash
# test-RABBIT-CAGE-16-first-stop-no-false-drift.sh
# Tests that sync-check.sh does NOT emit a "drift" systemMessage when
# CLAUDE.md simply does not exist (fresh install / first run).
#
# Bug (RABBIT-CAGE-16): On a fresh install/clone, sync-check.sh fires
# "Policy drift detected — CLAUDE.md regenerated from source files" even when
# CLAUDE.md simply doesn't exist. The condition `[ ! -f "$CLAUDE_MD" ]` and
# the drift branch use the SAME systemMessage, which is misleading.
#
# When CLAUDE.md is absent this is a first-run scenario, not a drift scenario.
# The hook MUST NOT emit the word "drift" in that case.
#
# These tests MUST FAIL against the current sync-check.sh (which does
# emit "drift detected" for absent CLAUDE.md). They turn green only after the
# hook is fixed to differentiate first-run from genuine drift.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.py"

FAILURES=0

ok() {
    echo "  PASS t$1: $2"
}

fail_t() {
    echo "  FAIL t$1: $2"
    FAILURES=$(( FAILURES + 1 ))
}

echo "test-RABBIT-CAGE-16-first-stop-no-false-drift.sh"
echo ""

# t1: sync-check.sh exists and is executable
if [ -f "$SYNC_CHECK" ] && [ -x "$SYNC_CHECK" ]; then
    ok 1 "sync-check.sh exists and is executable"
else
    fail_t 1 "sync-check.sh missing or not executable at $SYNC_CHECK"
fi

# Set up a minimal temporary RABBIT_ROOT — no CLAUDE.md (simulates fresh install)
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

# Create the minimal directory structure needed by sync-check.sh and generate-claude-md.sh
mkdir -p "$TMPROOT/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT/.claude/features/policy"

# Minimal policy files so generate-claude-md.sh can produce output
printf '# Philosophy\nMachine First.\n'    > "$TMPROOT/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'             > "$TMPROOT/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'           > "$TMPROOT/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'     > "$TMPROOT/.claude/features/policy/workflow-rules.md"

# Minimal policy-header.json so generate-claude-md.sh can read the header line
python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
    > "$TMPROOT/.claude/features/rabbit-cage/policy-header.json"

# Copy generate-claude-md.sh into the temp tree so sync-check.sh can invoke it
cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.py" \
   "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.py"
cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py" \
   "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py"

# Verify: CLAUDE.md does NOT exist in temp tree (simulates fresh install/clone)
if [ ! -f "$TMPROOT/CLAUDE.md" ]; then
    ok 2 "pre-condition: CLAUDE.md absent in temp workspace (fresh install scenario)"
else
    fail_t 2 "pre-condition failed: CLAUDE.md already exists in temp tree — test setup error"
fi

# Run sync-check.sh with RABBIT_SYNC_EVERY=1 so it fires (no counter skip)
sync_output=""
sync_exit=0
sync_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" \
    || sync_exit=$?

# t3: hook exits 0 (it should succeed; creating a missing CLAUDE.md is not an error)
if [ "$sync_exit" -eq 0 ]; then
    ok 3 "sync-check.sh exits 0 when CLAUDE.md is absent"
else
    fail_t 3 "sync-check.sh exited $sync_exit (expected 0)"
fi

# t4: CLAUDE.md was created (the hook should always create it when absent)
if [ -f "$TMPROOT/CLAUDE.md" ]; then
    ok 4 "CLAUDE.md was created by sync-check.sh when absent"
else
    fail_t 4 "CLAUDE.md was NOT created — hook did not write the file"
fi

# t5: The systemMessage MUST NOT contain the word "drift"
# This is the core regression: a missing CLAUDE.md is not drift, it is a first run.
# Current code uses the same branch/message for both cases → this test FAILS now.
sys_msg=""
sys_msg="$(echo "$sync_output" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('systemMessage', ''))
except Exception:
    pass
" 2>/dev/null)"

if echo "$sys_msg" | grep -qi 'drift'; then
    fail_t 5 "systemMessage contains 'drift' on first-run (absent CLAUDE.md) — should NOT; got: '$sys_msg'"
else
    ok 5 "systemMessage does NOT contain 'drift' on first-run (absent CLAUDE.md)"
fi

# t6: If a systemMessage is emitted, it should convey first-run / created semantics
# (e.g. "first run", "created", "initialized", or similar — NOT "drift").
# We check the positive: either it's empty or it contains a first-run-friendly term.
first_run_terms_regex='first.run\|creat\|initiali\|install'
if [ -z "$sys_msg" ] || echo "$sys_msg" | grep -qi "$first_run_terms_regex"; then
    ok 6 "systemMessage is absent or contains a first-run term (not a false drift alarm)"
else
    fail_t 6 "systemMessage is present but does not contain a first-run term; got: '$sys_msg'"
fi

echo ""
echo "Results: $(( 6 - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
