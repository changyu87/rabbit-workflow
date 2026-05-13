#!/usr/bin/env bash
# test-RABBIT-CAGE-23-rename-rbt-prefix.sh
# Tests for RABBIT-CAGE-23: rename rbt- prefixed runtime artifacts and env vars to rabbit- prefix.
#
# Spec invariants 31-35:
# 31. refresh.sh uses .rabbit-prompt-counter and RABBIT_REFRESH_EVERY
# 32. sync-check.sh uses .rabbit-sync-counter, RABBIT_SYNC_EVERY, .rabbit-prompt-counter, RABBIT_REFRESH_EVERY
# 33. settings.json declares RABBIT_REFRESH_EVERY and resets .rabbit-prompt-counter
# 34. rabbit-refresh.md resets .rabbit-prompt-counter
# 35. workspace-tree.sh excludes .rabbit-prompt-counter
#
# R3-compliant: no interactive constructs, fully automated.

set -u

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
REFRESH_SH="$REPO_ROOT/.claude/features/rabbit-cage/hooks/refresh.sh"
SYNC_CHECK="$REPO_ROOT/.claude/features/rabbit-cage/hooks/sync-check.sh"
SESSION_INIT="$REPO_ROOT/.claude/features/rabbit-cage/hooks/session-init.sh"
SETTINGS_JSON="$REPO_ROOT/.claude/features/rabbit-cage/settings.json"
RABBIT_REFRESH_MD="$REPO_ROOT/.claude/features/rabbit-cage/commands/rabbit-refresh.md"
WORKSPACE_TREE="$REPO_ROOT/.claude/features/rabbit-cage/scripts/workspace-tree.sh"
RABBIT_CONFIG_MD="$REPO_ROOT/.claude/features/rabbit-cage/commands/rabbit-config.md"

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

echo "test-RABBIT-CAGE-23-rename-rbt-prefix.sh"
echo ""

# ---------------------------------------------------------------------------
# t1: refresh.sh uses .rabbit-prompt-counter (not .rbt-prompt-counter)
# ---------------------------------------------------------------------------
echo "=== t1: refresh.sh uses .rabbit-prompt-counter (not .rbt-prompt-counter) ==="

if grep -q '\.rabbit-prompt-counter' "$REFRESH_SH" 2>/dev/null; then
    ok "refresh.sh references .rabbit-prompt-counter"
else
    fail_t "refresh.sh does NOT reference .rabbit-prompt-counter"
fi

if grep -q '\.rbt-prompt-counter' "$REFRESH_SH" 2>/dev/null; then
    fail_t "refresh.sh still references old .rbt-prompt-counter"
else
    ok "refresh.sh does NOT reference old .rbt-prompt-counter"
fi

# ---------------------------------------------------------------------------
# t2: refresh.sh uses RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY)
# ---------------------------------------------------------------------------
echo "=== t2: refresh.sh uses RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY) ==="

if grep -q 'RABBIT_REFRESH_EVERY' "$REFRESH_SH" 2>/dev/null; then
    ok "refresh.sh references RABBIT_REFRESH_EVERY"
else
    fail_t "refresh.sh does NOT reference RABBIT_REFRESH_EVERY"
fi

if grep -q 'RBT_REFRESH_EVERY' "$REFRESH_SH" 2>/dev/null; then
    fail_t "refresh.sh still references old RBT_REFRESH_EVERY"
else
    ok "refresh.sh does NOT reference old RBT_REFRESH_EVERY"
fi

# ---------------------------------------------------------------------------
# t3: sync-check.sh uses .rabbit-sync-counter (not .rbt-sync-counter)
# ---------------------------------------------------------------------------
echo "=== t3: sync-check.sh uses .rabbit-sync-counter (not .rbt-sync-counter) ==="

if grep -q '\.rabbit-sync-counter' "$SYNC_CHECK" 2>/dev/null; then
    ok "sync-check.sh references .rabbit-sync-counter"
else
    fail_t "sync-check.sh does NOT reference .rabbit-sync-counter"
fi

if grep -q '\.rbt-sync-counter' "$SYNC_CHECK" 2>/dev/null; then
    fail_t "sync-check.sh still references old .rbt-sync-counter"
else
    ok "sync-check.sh does NOT reference old .rbt-sync-counter"
fi

# ---------------------------------------------------------------------------
# t4: sync-check.sh uses RABBIT_SYNC_EVERY (not RBT_SYNC_EVERY)
# ---------------------------------------------------------------------------
echo "=== t4: sync-check.sh uses RABBIT_SYNC_EVERY (not RBT_SYNC_EVERY) ==="

if grep -q 'RABBIT_SYNC_EVERY' "$SYNC_CHECK" 2>/dev/null; then
    ok "sync-check.sh references RABBIT_SYNC_EVERY"
else
    fail_t "sync-check.sh does NOT reference RABBIT_SYNC_EVERY"
fi

if grep -q 'RBT_SYNC_EVERY' "$SYNC_CHECK" 2>/dev/null; then
    fail_t "sync-check.sh still references old RBT_SYNC_EVERY"
else
    ok "sync-check.sh does NOT reference old RBT_SYNC_EVERY"
fi

# ---------------------------------------------------------------------------
# t5: sync-check.sh uses .rabbit-prompt-counter (not .rbt-prompt-counter)
# ---------------------------------------------------------------------------
echo "=== t5: sync-check.sh uses .rabbit-prompt-counter on first-run/drift paths ==="

if grep -q '\.rabbit-prompt-counter' "$SYNC_CHECK" 2>/dev/null; then
    ok "sync-check.sh references .rabbit-prompt-counter"
else
    fail_t "sync-check.sh does NOT reference .rabbit-prompt-counter"
fi

if grep -q '\.rbt-prompt-counter' "$SYNC_CHECK" 2>/dev/null; then
    fail_t "sync-check.sh still references old .rbt-prompt-counter"
else
    ok "sync-check.sh does NOT reference old .rbt-prompt-counter"
fi

# ---------------------------------------------------------------------------
# t6: sync-check.sh uses RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY)
# ---------------------------------------------------------------------------
echo "=== t6: sync-check.sh uses RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY) ==="

if grep -q 'RABBIT_REFRESH_EVERY' "$SYNC_CHECK" 2>/dev/null; then
    ok "sync-check.sh references RABBIT_REFRESH_EVERY"
else
    fail_t "sync-check.sh does NOT reference RABBIT_REFRESH_EVERY"
fi

if grep -q 'RBT_REFRESH_EVERY' "$SYNC_CHECK" 2>/dev/null; then
    fail_t "sync-check.sh still references old RBT_REFRESH_EVERY"
else
    ok "sync-check.sh does NOT reference old RBT_REFRESH_EVERY"
fi

# ---------------------------------------------------------------------------
# t7: settings.json declares RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY)
# ---------------------------------------------------------------------------
echo "=== t7: settings.json declares RABBIT_REFRESH_EVERY ==="

if python3 -c "import json; d=json.load(open('$SETTINGS_JSON')); assert 'RABBIT_REFRESH_EVERY' in d.get('env',{})" 2>/dev/null; then
    ok "settings.json has RABBIT_REFRESH_EVERY in env"
else
    fail_t "settings.json does NOT have RABBIT_REFRESH_EVERY in env"
fi

if python3 -c "import json; d=json.load(open('$SETTINGS_JSON')); assert 'RBT_REFRESH_EVERY' not in d.get('env',{})" 2>/dev/null; then
    ok "settings.json does NOT have old RBT_REFRESH_EVERY in env"
else
    fail_t "settings.json still has old RBT_REFRESH_EVERY in env"
fi

# ---------------------------------------------------------------------------
# t8: settings.json SessionStart resets .rabbit-prompt-counter (not .rbt-prompt-counter)
# ---------------------------------------------------------------------------
echo "=== t8: settings.json SessionStart resets .rabbit-prompt-counter ==="

SETTINGS_JSON_CONTENT="$(cat "$SETTINGS_JSON")"

if printf '%s' "$SETTINGS_JSON_CONTENT" | grep -q '\.rabbit-prompt-counter' 2>/dev/null; then
    ok "settings.json references .rabbit-prompt-counter"
else
    fail_t "settings.json does NOT reference .rabbit-prompt-counter"
fi

if printf '%s' "$SETTINGS_JSON_CONTENT" | grep -q '\.rbt-prompt-counter' 2>/dev/null; then
    fail_t "settings.json still references old .rbt-prompt-counter"
else
    ok "settings.json does NOT reference old .rbt-prompt-counter"
fi

# ---------------------------------------------------------------------------
# t9: rabbit-refresh.md resets .rabbit-prompt-counter (not .rbt-prompt-counter)
# ---------------------------------------------------------------------------
echo "=== t9: rabbit-refresh.md resets .rabbit-prompt-counter ==="

if grep -q '\.rabbit-prompt-counter' "$RABBIT_REFRESH_MD" 2>/dev/null; then
    ok "rabbit-refresh.md references .rabbit-prompt-counter"
else
    fail_t "rabbit-refresh.md does NOT reference .rabbit-prompt-counter"
fi

if grep -q '\.rbt-prompt-counter' "$RABBIT_REFRESH_MD" 2>/dev/null; then
    fail_t "rabbit-refresh.md still references old .rbt-prompt-counter"
else
    ok "rabbit-refresh.md does NOT reference old .rbt-prompt-counter"
fi

# ---------------------------------------------------------------------------
# t10: workspace-tree.sh excludes .rabbit-prompt-counter (not .rbt-prompt-counter)
# ---------------------------------------------------------------------------
echo "=== t10: workspace-tree.sh excludes .rabbit-prompt-counter ==="

if grep -q '\.rabbit-prompt-counter' "$WORKSPACE_TREE" 2>/dev/null; then
    ok "workspace-tree.sh references .rabbit-prompt-counter"
else
    fail_t "workspace-tree.sh does NOT reference .rabbit-prompt-counter"
fi

if grep -q '\.rbt-prompt-counter' "$WORKSPACE_TREE" 2>/dev/null; then
    fail_t "workspace-tree.sh still references old .rbt-prompt-counter"
else
    ok "workspace-tree.sh does NOT reference old .rbt-prompt-counter"
fi

# ---------------------------------------------------------------------------
# t11: rabbit-config.md uses RABBIT_REFRESH_EVERY (not RBT_REFRESH_EVERY)
# ---------------------------------------------------------------------------
echo "=== t11: rabbit-config.md uses RABBIT_REFRESH_EVERY ==="

if grep -q 'RABBIT_REFRESH_EVERY' "$RABBIT_CONFIG_MD" 2>/dev/null; then
    ok "rabbit-config.md references RABBIT_REFRESH_EVERY"
else
    fail_t "rabbit-config.md does NOT reference RABBIT_REFRESH_EVERY"
fi

if grep -q 'RBT_REFRESH_EVERY' "$RABBIT_CONFIG_MD" 2>/dev/null; then
    fail_t "rabbit-config.md still references old RBT_REFRESH_EVERY"
else
    ok "rabbit-config.md does NOT reference old RBT_REFRESH_EVERY"
fi

# ---------------------------------------------------------------------------
# t12: deployed .claude/hooks/refresh.sh uses new names (not rbt-)
# ---------------------------------------------------------------------------
echo "=== t12: deployed refresh.sh uses new names ==="

DEPLOYED_REFRESH="$REPO_ROOT/.claude/hooks/refresh.sh"
if [ -f "$DEPLOYED_REFRESH" ]; then
    if grep -q '\.rbt-prompt-counter\|RBT_REFRESH_EVERY' "$DEPLOYED_REFRESH" 2>/dev/null; then
        fail_t "deployed refresh.sh still references old rbt- names"
    else
        ok "deployed refresh.sh does NOT reference old rbt- names"
    fi
else
    ok "deployed refresh.sh not present (symlink or absent — skipping)"
fi

# ---------------------------------------------------------------------------
# t13: deployed .claude/hooks/sync-check.sh uses new names (not rbt-)
# ---------------------------------------------------------------------------
echo "=== t13: deployed sync-check.sh uses new names ==="

DEPLOYED_SYNC="$REPO_ROOT/.claude/hooks/sync-check.sh"
if [ -f "$DEPLOYED_SYNC" ]; then
    if grep -q '\.rbt-sync-counter\|\.rbt-prompt-counter\|RBT_SYNC_EVERY\|RBT_REFRESH_EVERY' "$DEPLOYED_SYNC" 2>/dev/null; then
        fail_t "deployed sync-check.sh still references old rbt- names"
    else
        ok "deployed sync-check.sh does NOT reference old rbt- names"
    fi
else
    ok "deployed sync-check.sh not present (symlink or absent — skipping)"
fi

# ---------------------------------------------------------------------------
# t14: deployed .claude/settings.json uses new names (not rbt-)
# ---------------------------------------------------------------------------
echo "=== t14: deployed settings.json uses new names ==="

DEPLOYED_SETTINGS="$REPO_ROOT/.claude/settings.json"
# Resolve symlink to check actual content
if [ -L "$DEPLOYED_SETTINGS" ]; then
    DEPLOYED_SETTINGS_REAL="$(readlink -f "$DEPLOYED_SETTINGS")"
else
    DEPLOYED_SETTINGS_REAL="$DEPLOYED_SETTINGS"
fi

if [ -f "$DEPLOYED_SETTINGS_REAL" ]; then
    if grep -q 'RBT_REFRESH_EVERY\|\.rbt-prompt-counter' "$DEPLOYED_SETTINGS_REAL" 2>/dev/null; then
        fail_t "deployed settings.json still references old rbt- names"
    else
        ok "deployed settings.json does NOT reference old rbt- names"
    fi
else
    ok "deployed settings.json not present — skipping"
fi

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
