#!/usr/bin/env bash
# test-RABBIT-CAGE-12-counter-reset.sh
# Tests that rbt-sync-check.sh writes RBT_REFRESH_EVERY to .rbt-prompt-counter
# when drift is detected, so that rbt-refresh.sh fires injection on the very
# next UserPromptSubmit.
#
# Bug (reopened): rbt-sync-check.sh writes 0 to .rbt-prompt-counter on drift.
# rbt-refresh.sh fires only when counter >= RBT_REFRESH_EVERY (default 20).
# counter=0 → next increment = 1 → 1 < 20 → injection does NOT fire.
#
# Correct fix: write RBT_REFRESH_EVERY (20) to .rbt-prompt-counter so that
# rbt-refresh.sh reads 20, increments to 21, 21 >= 20 → injection fires.
#
# t5 (updated), t6, and t7 are RED against the current (unfixed) implementation.
# t5–t7 turn green only after the fix is applied.
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

# t5 (updated): .rbt-prompt-counter must equal RBT_REFRESH_EVERY (20) after drift,
#   NOT 0. Writing 0 means rbt-refresh.sh won't fire on the next prompt.
EXPECTED_COUNTER="${RBT_REFRESH_EVERY:-20}"
post_value="$(cat "$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]')"
if [ "$post_value" = "$EXPECTED_COUNTER" ]; then
    ok 5 ".rbt-prompt-counter was set to RBT_REFRESH_EVERY ($EXPECTED_COUNTER) after drift"
else
    fail_t 5 ".rbt-prompt-counter is '$post_value' (expected $EXPECTED_COUNTER) — rbt-sync-check.sh must write threshold, not 0"
fi

# t6: same assertion stated explicitly for new readers — counter equals threshold
if [ "$post_value" = "$EXPECTED_COUNTER" ]; then
    ok 6 ".rbt-prompt-counter equals RBT_REFRESH_EVERY ($EXPECTED_COUNTER), not 0"
else
    fail_t 6 ".rbt-prompt-counter is '$post_value' (expected $EXPECTED_COUNTER) — injection will not fire on next prompt"
fi

# t7: simulate the next UserPromptSubmit — run rbt-refresh.sh with the current
#   counter value; verify it emits output containing 'additionalContext'.
#   For this to work, CLAUDE.md must contain at least one @-import line.
#   We add one pointing at a real file in the temp tree.
REFRESH_HOOK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/rbt-refresh.sh"
# Create a minimal policy file the import can resolve
mkdir -p "$TMPROOT/.claude/features/policy"
printf '# Stub policy\nstub content\n' > "$TMPROOT/.claude/features/policy/stub.md"
# Write a CLAUDE.md with an @-import that rbt-refresh.sh can read
printf '@.claude/features/policy/stub.md\n' > "$TMPROOT/CLAUDE.md"
# Seed counter at the threshold value (what the fix should write)
printf '%s\n' "$EXPECTED_COUNTER" > "$COUNTER_FILE"

refresh_output=""
refresh_exit=0
refresh_output="$(RABBIT_ROOT="$TMPROOT" RBT_REFRESH_EVERY="$EXPECTED_COUNTER" bash "$REFRESH_HOOK" 2>/dev/null)" || refresh_exit=$?

if echo "$refresh_output" | grep -q 'additionalContext'; then
    ok 7 "rbt-refresh.sh emits 'additionalContext' on the next UserPromptSubmit (injection fires)"
else
    fail_t 7 "rbt-refresh.sh did NOT emit 'additionalContext' — counter=$EXPECTED_COUNTER should trigger injection but did not (output: '$refresh_output')"
fi

echo ""
echo "Results: $(( 7 - FAILURES )) passed, $FAILURES failed"

if [ "$FAILURES" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$FAILURES TEST(S) FAILED"
    exit 1
fi
