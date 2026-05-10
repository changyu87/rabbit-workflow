#!/usr/bin/env bash
# test-RABBIT-CAGE-12-counter-reset.sh
# Tests that rbt-sync-check.sh resets .rbt-prompt-counter to 0 when drift is detected.
#
# Bug: rbt-sync-check.sh regenerates CLAUDE.md on drift but does not reset
# .rbt-prompt-counter. Without the reset, rbt-refresh.sh (UserPromptSubmit)
# will not inject the fresh policy on the next user prompt.
#
# Planned fix: after regenerating CLAUDE.md, rbt-sync-check.sh should write 0
# to .rbt-prompt-counter so the next user prompt triggers a policy re-injection.
#
# This test MUST exit 1 (FAIL) against the current (unfixed) rbt-sync-check.sh.
# It will pass only after the planned fix is applied.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/rbt-sync-check.sh"

FAILURES=0

ok() {
    echo "  PASS t$1: $2"
}

fail_t() {
    echo "  FAIL t$1: $2"
    FAILURES=$(( FAILURES + 1 ))
}

echo "test-RABBIT-CAGE-12-counter-reset.sh"
echo ""

# t1: rbt-sync-check.sh exists and is executable
if [ -f "$SYNC_CHECK" ] && [ -x "$SYNC_CHECK" ]; then
    ok 1 "rbt-sync-check.sh exists and is executable"
else
    fail_t 1 "rbt-sync-check.sh missing or not executable at $SYNC_CHECK"
fi

# Set up a temporary RABBIT_ROOT to isolate the test
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

# Create the minimal directory structure
mkdir -p "$TMPROOT/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT/.claude/features/policy"
mkdir -p "$TMPROOT/.claude/features/rabbit-cage"

# Create fake policy files (minimal, distinct content)
printf '# Philosophy\nMachine First.\n' > "$TMPROOT/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'          > "$TMPROOT/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'        > "$TMPROOT/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'  > "$TMPROOT/.claude/features/policy/workflow-rules.md"

# Create a fake policy-header.json so generate-claude-md.sh can run
python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
    > "$TMPROOT/.claude/features/rabbit-cage/policy-header.json"

# Copy generate-claude-md.sh into the temp tree so rbt-sync-check.sh can invoke it
cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
   "$TMPROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

# Create a CLAUDE.md with stale/different content to guarantee drift is detected
printf 'STALE CONTENT — does not match generated output\n' > "$TMPROOT/CLAUDE.md"

# Seed .rbt-prompt-counter with a non-zero value (simulates an active session)
COUNTER_FILE="$TMPROOT/.rbt-prompt-counter"
printf '15\n' > "$COUNTER_FILE"

# t2: pre-condition — counter file exists with non-zero value
pre_value="$(cat "$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]')"
if [ "$pre_value" != "0" ]; then
    ok 2 "pre-condition: .rbt-prompt-counter is non-zero ($pre_value)"
else
    fail_t 2 "pre-condition: .rbt-prompt-counter is already 0 — test setup error"
fi

# t3: rbt-sync-check.sh exits 0 in the temp environment
sync_exit=0
RABBIT_ROOT="$TMPROOT" bash "$SYNC_CHECK" > /dev/null 2>&1 || sync_exit=$?
if [ "$sync_exit" -eq 0 ]; then
    ok 3 "rbt-sync-check.sh exits 0"
else
    fail_t 3 "rbt-sync-check.sh exited $sync_exit (expected 0)"
fi

# t4: CLAUDE.md was regenerated (content changed from stale value)
if [ -f "$TMPROOT/CLAUDE.md" ] && ! grep -q "^STALE CONTENT" "$TMPROOT/CLAUDE.md" 2>/dev/null; then
    ok 4 "CLAUDE.md was regenerated (drift was detected and fixed)"
else
    fail_t 4 "CLAUDE.md was NOT regenerated — drift detection did not fire; check generate-claude-md.sh setup in tmproot"
fi

# t5 (the key assertion): .rbt-prompt-counter must be 0 after drift is detected
post_value="$(cat "$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]')"
if [ "$post_value" = "0" ]; then
    ok 5 ".rbt-prompt-counter was reset to 0 after drift was detected"
else
    fail_t 5 ".rbt-prompt-counter is '$post_value' (expected 0) — rbt-sync-check.sh does not reset it on drift"
fi

echo ""
echo "Results: $(( 5 - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
