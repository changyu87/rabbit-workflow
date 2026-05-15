#!/usr/bin/env bash
# rabbit-cage generate-claude-md tests
# Tests for generate-claude-md.sh script and related infrastructure.
# All tests must FAIL before implementation.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
CAGE_DIR="$REPO_ROOT/.claude/features/rabbit-cage"
GENERATE_SCRIPT="$CAGE_DIR/scripts/generate-claude-md.py"
SYNC_HOOK="$CAGE_DIR/hooks/sync-check.py"
SETTINGS_JSON="$REPO_ROOT/.claude/settings.json"

pass=0
fail=0

ok() {
    echo "  PASS t$1: $2"
    pass=$((pass + 1))
}

fail_t() {
    echo "  FAIL t$1: $2"
    fail=$((fail + 1))
}

echo "test-generate-claude-md.sh"

# ─── Infrastructure existence (t1–t4) ───────────────────────────────────────

# t1: generate-claude-md.sh exists and is executable
if [ -f "$GENERATE_SCRIPT" ] && [ -x "$GENERATE_SCRIPT" ]; then
    ok 1 "generate-claude-md.sh exists and is executable"
else
    fail_t 1 "generate-claude-md.sh missing or not executable"
fi

# t2: sync-check.sh exists and is executable
if [ -f "$SYNC_HOOK" ] && [ -x "$SYNC_HOOK" ]; then
    ok 2 "sync-check.sh exists and is executable"
else
    fail_t 2 "sync-check.sh missing or not executable"
fi

# t3: settings.json contains the string "Stop" (PreToolUse matcher or Stop event)
if grep -q '"Stop"' "$SETTINGS_JSON" 2>/dev/null; then
    ok 3 "settings.json contains \"Stop\""
else
    fail_t 3 "settings.json does not contain \"Stop\""
fi

# t4: .gitignore at repo root does NOT contain "CLAUDE.md" (BACKLOG-13: CLAUDE.md is now committed)
if ! grep -qxF 'CLAUDE.md' "$REPO_ROOT/.gitignore" 2>/dev/null; then
    ok 4 ".gitignore does NOT contain CLAUDE.md (committed to git per BACKLOG-13)"
else
    fail_t 4 ".gitignore still lists CLAUDE.md — must be removed so file can be committed"
fi

# ─── generate-claude-md.sh output (t5–t8) ───────────────────────────────────

# Run the script and capture combined stdout+stderr; check exit code.
GENERATED_OUTPUT=""
GENERATE_OK=false
if [ -x "$GENERATE_SCRIPT" ]; then
    if GENERATED_OUTPUT="$("$GENERATE_SCRIPT" 2>&1)"; then
        GENERATE_OK=true
    fi
fi

# t5: output contains the sync start marker "rabbit-policy-start"
if $GENERATE_OK; then
    if echo "$GENERATED_OUTPUT" | grep -q 'rabbit-policy-start'; then
        ok 5 "output contains 'rabbit-policy-start'"
    else
        fail_t 5 "output does not contain 'rabbit-policy-start'"
    fi
else
    fail_t 5 "generate-claude-md.sh missing or failed"
fi

# t6: output contains "Machine First" (verbatim content from philosophy.md)
if $GENERATE_OK; then
    if echo "$GENERATED_OUTPUT" | grep -q 'Machine First'; then
        ok 6 "output contains 'Machine First'"
    else
        fail_t 6 "output does not contain 'Machine First'"
    fi
else
    fail_t 6 "generate-claude-md.sh missing or failed"
fi

# t7: output contains "# Spec Rules" (H1 heading from spec-rules.md)
if $GENERATE_OK; then
    if echo "$GENERATED_OUTPUT" | grep -q '# Spec Rules'; then
        ok 7 "output contains '# Spec Rules'"
    else
        fail_t 7 "output does not contain '# Spec Rules'"
    fi
else
    fail_t 7 "generate-claude-md.sh missing or failed"
fi

# t8: output does NOT contain "@./.claude/policy" (no @-import lines in generated output)
if $GENERATE_OK; then
    if ! echo "$GENERATED_OUTPUT" | grep -q '@\./.claude/policy'; then
        ok 8 "output does not contain '@./.claude/policy' (@-import lines absent)"
    else
        fail_t 8 "output still contains '@./.claude/policy' (@-import lines not expanded)"
    fi
else
    fail_t 8 "generate-claude-md.sh missing or failed"
fi

# ─── run.sh registration (t9) ───────────────────────────────────────────────

# t9: run.sh includes "test-generate-claude-md.sh"
RUN_SH="$CAGE_DIR/test/run.sh"
if grep -q 'test-generate-claude-md.sh' "$RUN_SH" 2>/dev/null; then
    ok 9 "test-generate-claude-md.sh is registered in run.sh"
else
    fail_t 9 "test-generate-claude-md.sh is NOT registered in run.sh"
fi

# t10: policy-header.json is valid JSON
POLICY_HEADER="$REPO_ROOT/.claude/features/rabbit-cage/policy-header.json"
if python3 -c "import json; json.load(open('$POLICY_HEADER'))" 2>/dev/null; then
    ok 10 "policy-header.json is valid JSON"
else
    fail_t 10 "policy-header.json does not exist or is not valid JSON"
fi

# t11: policy-header.json has required fields: header and version
if python3 -c "
import json, sys
d = json.load(open('$POLICY_HEADER'))
assert 'header' in d, 'missing header field'
assert 'version' in d, 'missing version field'
assert d['header'].startswith('#'), 'header must start with #'
" 2>/dev/null; then
    ok 11 "policy-header.json has required fields: header (starts with #) and version"
else
    fail_t 11 "policy-header.json missing required fields or header does not start with #"
fi

# t12: generate-claude-md.sh output first line matches header field from policy-header.json
EXPECTED_HEADER="$(python3 -c "import json; print(json.load(open('$POLICY_HEADER'))['header'])" 2>/dev/null)" || true
ACTUAL_FIRST="$(python3 "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.py" 2>/dev/null | head -1)" || true
if [ "$EXPECTED_HEADER" = "$ACTUAL_FIRST" ]; then
    ok 12 "generate-claude-md.sh first line matches policy-header.json header field"
else
    fail_t 12 "generate-claude-md.sh first line does not match policy-header.json header field"
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
