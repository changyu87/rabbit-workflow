#!/usr/bin/env bash
# test-RABBIT-CAGE-21-plugin-change-alert.sh
# Tests that sync-check.sh emits a one-time green [rabbit] systemMessage when
# .rabbit-skills-updated marker exists, naming the updated skills.
#
# Spec invariant 24 (updated by RABBIT-CAGE-24): On Stop, sync-check.sh checks
# for .rabbit-skills-updated marker:
# (a) If marker exists: emit green [rabbit] systemMessage naming skills +
#     "will reload automatically on next invocation", then DELETE marker.
# (b) If marker absent: silent.
# (c) Self-clearing: second invocation after deletion is silent.
# (d) Single-JSON-per-invocation invariant preserved.
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.py"

FAILURES=0
TOTAL=0

ok() { TOTAL=$(( TOTAL + 1 )); echo "  PASS t$TOTAL: $1"; }
fail_t() { TOTAL=$(( TOTAL + 1 )); FAILURES=$(( FAILURES + 1 )); echo "  FAIL t$TOTAL: $1"; }

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
    python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
        > "$d/.claude/features/rabbit-cage/policy-header.json"
    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.py" \
       "$d/.claude/features/rabbit-cage/scripts/generate-claude-md.py"
    cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py" \
       "$d/.claude/features/rabbit-cage/scripts/generate-claude-md-header.py"
    python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
        > "$d/.claude/features/registry.json"
    local correct
    correct="$(RABBIT_ROOT="$d" python3 "$d/.claude/features/rabbit-cage/scripts/generate-claude-md.py" 2>/dev/null)"
    printf '%s\n' "$correct" > "$d/CLAUDE.md"
    git -C "$d" add -A
    git -C "$d" commit -q -m "init"
    echo "$d"
}

echo "test-RABBIT-CAGE-21-plugin-change-alert.sh"
echo ""

TMPROOT="" TMPROOT2=""

# ---------------------------------------------------------------------------
# t1: .rabbit-skills-updated exists → [rabbit] systemMessage emitted
# ---------------------------------------------------------------------------
echo "=== t1: .rabbit-skills-updated exists → [rabbit] notification emitted ==="
TMPROOT="$(make_clean_repo)"
trap 'rm -rf "$TMPROOT" "$TMPROOT2"' EXIT
printf 'rabbit-bug\n' > "$TMPROOT/.rabbit-skills-updated"
t1_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
t1_msg="$(printf '%s' "$t1_output" | extract_sys_msg)"
if printf '%s' "$t1_msg" | grep -q '\[rabbit\]'; then
    ok "systemMessage contains '[rabbit]'"
else
    fail_t "systemMessage does NOT contain '[rabbit]' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t2: Message contains the skill name
# ---------------------------------------------------------------------------
echo "=== t2: notification contains the skill name ==="
if printf '%s' "$t1_msg" | grep -q 'rabbit-bug'; then
    ok "systemMessage contains 'rabbit-bug'"
else
    fail_t "systemMessage does NOT contain skill name 'rabbit-bug' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t3: Message mentions "next invocation" (correct prescription)
# ---------------------------------------------------------------------------
echo "=== t3: notification says 'next invocation' ==="
if printf '%s' "$t1_msg" | grep -q 'next invocation'; then
    ok "systemMessage contains 'next invocation'"
else
    fail_t "systemMessage does NOT say 'next invocation' (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t4: Message is green (spec invariant 18)
# ---------------------------------------------------------------------------
echo "=== t4: notification is green (ANSI invariant 18) ==="
t4_green="$(MSG="$t1_msg" python3 -c "
import os; msg=os.environ.get('MSG','')
print('yes' if '\x1b[32m' in msg and '\x1b[0m' in msg else 'no')
" 2>/dev/null)"
if [ "$t4_green" = "yes" ]; then
    ok "notification is green (ANSI \x1b[32m)"
else
    fail_t "notification is NOT green (actual: $(printf '%q' "$t1_msg"))"
fi

# ---------------------------------------------------------------------------
# t5: .rabbit-skills-updated is DELETED after sync-check runs (self-clearing)
# ---------------------------------------------------------------------------
echo "=== t5: .rabbit-skills-updated deleted after notification (self-clearing) ==="
if [ -f "$TMPROOT/.rabbit-skills-updated" ]; then
    fail_t ".rabbit-skills-updated still exists after sync-check — must be self-clearing"
else
    ok ".rabbit-skills-updated deleted by sync-check"
fi

# ---------------------------------------------------------------------------
# t6: Second run of sync-check (marker deleted) → no notification
# ---------------------------------------------------------------------------
echo "=== t6: second sync-check run → silent (marker already consumed) ==="
t6_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
t6_msg="$(printf '%s' "$t6_output" | extract_sys_msg)"
if printf '%s' "$t6_msg" | grep -q 'Skills updated\|rabbit-bug\|next invocation'; then
    fail_t "notification fired again on second run — must be one-time only"
else
    ok "no notification on second run (self-clearing confirmed)"
fi

# ---------------------------------------------------------------------------
# t7: .rabbit-skills-updated absent → silent
# ---------------------------------------------------------------------------
echo "=== t7: .rabbit-skills-updated absent → no notification ==="
TMPROOT2="$(make_clean_repo)"
rm -f "$TMPROOT2/.rabbit-skills-updated"
t7_output="$(RABBIT_ROOT="$TMPROOT2" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
t7_msg="$(printf '%s' "$t7_output" | extract_sys_msg)"
if printf '%s' "$t7_msg" | grep -q 'Skills updated\|next invocation'; then
    fail_t "notification fired when .rabbit-skills-updated was absent (false positive)"
else
    ok "no notification when .rabbit-skills-updated is absent"
fi

# ---------------------------------------------------------------------------
# t8: sync-check.sh does NOT reference .rabbit-plugins-stale
# ---------------------------------------------------------------------------
echo "=== t8: sync-check.sh does NOT reference .rabbit-plugins-stale ==="
if grep -q '\.rabbit-plugins-stale' "$SYNC_CHECK" 2>/dev/null; then
    fail_t "sync-check.sh still references .rabbit-plugins-stale — must be fully removed"
else
    ok "sync-check.sh has no .rabbit-plugins-stale reference"
fi

# ---------------------------------------------------------------------------
# t9: Single-JSON-per-invocation invariant — output is valid JSON or empty
# ---------------------------------------------------------------------------
echo "=== t9: sync-check.sh emits at most one JSON object (single-JSON invariant) ==="
printf 'rabbit-cage\n' > "$TMPROOT/.rabbit-skills-updated"
t9_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
t9_count="$(printf '%s' "$t9_output" | python3 -c "
import sys, json
data = sys.stdin.read().strip()
if not data:
    print(0)
    sys.exit(0)
try:
    json.loads(data)
    print(1)
except Exception:
    dec = json.JSONDecoder(); idx=0; count=0
    while idx < len(data):
        sl = data[idx:].lstrip()
        if not sl: break
        try:
            _, end = dec.raw_decode(sl)
            count += 1; idx += len(data)-len(data[idx:])+end
        except: break
    print(count)
" 2>/dev/null)"
if [ "$t9_count" = "1" ] || [ "$t9_count" = "0" ]; then
    ok "at most one JSON object emitted (count=$t9_count)"
else
    fail_t "more than one JSON object emitted (count=$t9_count) — violates single-JSON invariant"
fi

# ---------------------------------------------------------------------------
# t10: Multiple skill names appear comma-separated in message
# ---------------------------------------------------------------------------
echo "=== t10: multiple skill names shown comma-separated ==="
printf 'rabbit-bug\nrabbit-cage\n' > "$TMPROOT/.rabbit-skills-updated"
t10_output="$(RABBIT_ROOT="$TMPROOT" RABBIT_SYNC_EVERY=1 python3 "$SYNC_CHECK" 2>/dev/null)" || true
t10_msg="$(printf '%s' "$t10_output" | extract_sys_msg)"
if printf '%s' "$t10_msg" | grep -q 'rabbit-bug' && printf '%s' "$t10_msg" | grep -q 'rabbit-cage'; then
    ok "both skill names appear in message"
else
    fail_t "not all skill names appear in message (actual: $(printf '%q' "$t10_msg"))"
fi

rm -rf "$TMPROOT" "$TMPROOT2" 2>/dev/null || true
trap - EXIT
echo ""
echo "Results: $(( TOTAL - FAILURES )) passed, $FAILURES failed"
[ "$FAILURES" -eq 0 ] && { echo "ALL TESTS PASSED"; exit 0; } || { echo "$FAILURES TEST(S) FAILED"; exit 1; }
