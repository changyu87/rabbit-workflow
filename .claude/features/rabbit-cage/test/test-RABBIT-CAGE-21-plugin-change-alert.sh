#!/usr/bin/env bash
# test-RABBIT-CAGE-21-plugin-change-alert.sh
# Tests that sync-check.sh emits a green [rabbit] systemMessage when plugins were updated.
#
# Spec invariant 24 (updated by RABBIT-CAGE-22): On every Stop, after existing drift checks,
# sync-check.sh checks for .rabbit-plugins-stale marker:
# (a) If .rabbit-plugins-stale exists: emit green [rabbit] systemMessage instructing /rabbit-refresh.
# (b) If .rabbit-plugins-stale absent: silent (no output / no plugin alert).
# (c) Single-JSON-per-invocation invariant preserved.
#
# Note: RABBIT-CAGE-21 originally tested the git-diff mechanism replaced by RABBIT-CAGE-22.
# This test now validates the same feature (plugin-change alert) under the new model.
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

# Build a minimal temp git repo with CLAUDE.md matching generated output.
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

echo "test-RABBIT-CAGE-21-plugin-change-alert.sh"
echo ""

TMPROOT=""
TMPROOT2=""

# ---------------------------------------------------------------------------
# t1: When .rabbit-plugins-stale exists, sync-check.sh emits [rabbit] systemMessage
# ---------------------------------------------------------------------------
echo "=== t1: .rabbit-plugins-stale exists → [rabbit] plugin-change alert ==="

TMPROOT="$(make_clean_repo)"
trap 'rm -rf "$TMPROOT" "$TMPROOT2"' EXIT

touch "$TMPROOT/.rabbit-plugins-stale"

t1_output="$(RABBIT_ROOT="$TMPROOT" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t1_msg="$(printf '%s' "$t1_output" | extract_sys_msg)"

if printf '%s' "$t1_msg" | grep -q '\[rabbit\]' 2>/dev/null; then
    ok "systemMessage contains '[rabbit]'"
else
    fail_t "systemMessage does NOT contain '[rabbit]' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t2: The message mentions /rabbit-refresh
# ---------------------------------------------------------------------------
echo "=== t2: plugin-change alert contains 'rabbit-refresh' ==="

if printf '%s' "$t1_msg" | grep -q 'rabbit-refresh' 2>/dev/null; then
    ok "systemMessage contains 'rabbit-refresh'"
else
    fail_t "systemMessage does NOT contain 'rabbit-refresh' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t3: The message is green (info convention, spec invariant 18)
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
# t4: sync-check.sh does NOT use git merge-base / git diff for plugin detection
# (old git-diff mechanism removed in RABBIT-CAGE-22)
# ---------------------------------------------------------------------------
echo "=== t4: sync-check.sh does NOT contain git merge-base plugin detection ==="

if grep -q 'merge-base.*main\|git diff.*skills\|git diff.*commands' "$SYNC_CHECK" 2>/dev/null; then
    fail_t "sync-check.sh still contains git merge-base/diff plugin detection (must use .rabbit-plugins-stale marker)"
else
    ok "sync-check.sh does not use git merge-base/diff for plugin detection"
fi

# ---------------------------------------------------------------------------
# t5: When .rabbit-plugins-stale absent, no plugin alert fires
# ---------------------------------------------------------------------------
echo "=== t5: .rabbit-plugins-stale absent → no plugin alert ==="

TMPROOT2="$(make_clean_repo)"
rm -f "$TMPROOT2/.rabbit-plugins-stale"

t5_output="$(RABBIT_ROOT="$TMPROOT2" RBT_SYNC_EVERY=1 bash "$SYNC_CHECK" 2>/dev/null)" || true
t5_msg="$(printf '%s' "$t5_output" | extract_sys_msg)"

if printf '%s' "$t5_msg" | grep -q 'rabbit-refresh\|reload-plugins\|Plugins updated' 2>/dev/null; then
    fail_t "plugin alert fired when .rabbit-plugins-stale was absent (false positive)"
else
    ok "no plugin alert when .rabbit-plugins-stale is absent"
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
    try:
        json.loads(data)
        print(1)
    except Exception:
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
