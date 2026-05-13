#!/usr/bin/env bash
# test-RABBIT-CAGE-23-rename-rbt-prefix.sh
# Tests for RABBIT-CAGE-23: rename rbt- prefixed runtime artifacts and env vars to rabbit- prefix.
#
# Spec invariants 31-36:
# 31. refresh.sh uses .rabbit-prompt-counter and RABBIT_REFRESH_EVERY
# 32. sync-check.sh uses .rabbit-sync-counter, RABBIT_SYNC_EVERY, .rabbit-prompt-counter, RABBIT_REFRESH_EVERY
# 33. settings.json declares RABBIT_REFRESH_EVERY and resets .rabbit-prompt-counter
# 34. rabbit-refresh.md resets .rabbit-prompt-counter
# 35. workspace-tree.sh excludes .rabbit-prompt-counter (not .rbt-prompt-counter)
# 36. session-init.sh migrates legacy .rbt-* counter files to .rabbit-* names
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
# t12: session-init.sh migrates .rbt-prompt-counter -> .rabbit-prompt-counter
# ---------------------------------------------------------------------------
echo "=== t12: session-init.sh migrates legacy .rbt-prompt-counter ==="

TMPROOT_MIGRATE=""
TMPROOT_MIGRATE="$(mktemp -d)"
git init -q "$TMPROOT_MIGRATE"
git -C "$TMPROOT_MIGRATE" config user.email "test@test.com"
git -C "$TMPROOT_MIGRATE" config user.name "Test"
git -C "$TMPROOT_MIGRATE" checkout -q -b main 2>/dev/null || true

mkdir -p "$TMPROOT_MIGRATE/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT_MIGRATE/.claude/features/policy"

printf '# Philosophy\nMachine First.\n'   > "$TMPROOT_MIGRATE/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'            > "$TMPROOT_MIGRATE/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'          > "$TMPROOT_MIGRATE/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'    > "$TMPROOT_MIGRATE/.claude/features/policy/workflow-rules.md"

python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
    > "$TMPROOT_MIGRATE/.claude/features/rabbit-cage/policy-header.json"

cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
   "$TMPROOT_MIGRATE/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
    > "$TMPROOT_MIGRATE/.claude/features/registry.json"

CORRECT="$(RABBIT_ROOT="$TMPROOT_MIGRATE" bash "$TMPROOT_MIGRATE/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$CORRECT" > "$TMPROOT_MIGRATE/CLAUDE.md"

git -C "$TMPROOT_MIGRATE" add -A
git -C "$TMPROOT_MIGRATE" commit -q -m "init"

# Place legacy counter file
printf '5\n' > "$TMPROOT_MIGRATE/.rbt-prompt-counter"

# Run session-init.sh
RABBIT_ROOT="$TMPROOT_MIGRATE" bash "$SESSION_INIT" >/dev/null 2>&1 || true

if [ -f "$TMPROOT_MIGRATE/.rabbit-prompt-counter" ]; then
    ok "session-init.sh created .rabbit-prompt-counter from legacy .rbt-prompt-counter"
else
    fail_t "session-init.sh did NOT create .rabbit-prompt-counter from legacy .rbt-prompt-counter"
fi

if [ ! -f "$TMPROOT_MIGRATE/.rbt-prompt-counter" ]; then
    ok "session-init.sh removed legacy .rbt-prompt-counter after migration"
else
    fail_t "session-init.sh did NOT remove legacy .rbt-prompt-counter after migration"
fi

rm -rf "$TMPROOT_MIGRATE"

# ---------------------------------------------------------------------------
# t13: session-init.sh migrates .rbt-sync-counter -> .rabbit-sync-counter
# ---------------------------------------------------------------------------
echo "=== t13: session-init.sh migrates legacy .rbt-sync-counter ==="

TMPROOT_MIGRATE2=""
TMPROOT_MIGRATE2="$(mktemp -d)"
git init -q "$TMPROOT_MIGRATE2"
git -C "$TMPROOT_MIGRATE2" config user.email "test@test.com"
git -C "$TMPROOT_MIGRATE2" config user.name "Test"
git -C "$TMPROOT_MIGRATE2" checkout -q -b main 2>/dev/null || true

mkdir -p "$TMPROOT_MIGRATE2/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT_MIGRATE2/.claude/features/policy"

printf '# Philosophy\nMachine First.\n'   > "$TMPROOT_MIGRATE2/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'            > "$TMPROOT_MIGRATE2/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'          > "$TMPROOT_MIGRATE2/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'    > "$TMPROOT_MIGRATE2/.claude/features/policy/workflow-rules.md"

python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
    > "$TMPROOT_MIGRATE2/.claude/features/rabbit-cage/policy-header.json"

cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
   "$TMPROOT_MIGRATE2/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
    > "$TMPROOT_MIGRATE2/.claude/features/registry.json"

CORRECT2="$(RABBIT_ROOT="$TMPROOT_MIGRATE2" bash "$TMPROOT_MIGRATE2/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$CORRECT2" > "$TMPROOT_MIGRATE2/CLAUDE.md"

git -C "$TMPROOT_MIGRATE2" add -A
git -C "$TMPROOT_MIGRATE2" commit -q -m "init"

# Place legacy counter file
printf '3\n' > "$TMPROOT_MIGRATE2/.rbt-sync-counter"

# Run session-init.sh
RABBIT_ROOT="$TMPROOT_MIGRATE2" bash "$SESSION_INIT" >/dev/null 2>&1 || true

if [ -f "$TMPROOT_MIGRATE2/.rabbit-sync-counter" ]; then
    ok "session-init.sh created .rabbit-sync-counter from legacy .rbt-sync-counter"
else
    fail_t "session-init.sh did NOT create .rabbit-sync-counter from legacy .rbt-sync-counter"
fi

if [ ! -f "$TMPROOT_MIGRATE2/.rbt-sync-counter" ]; then
    ok "session-init.sh removed legacy .rbt-sync-counter after migration"
else
    fail_t "session-init.sh did NOT remove legacy .rbt-sync-counter after migration"
fi

rm -rf "$TMPROOT_MIGRATE2"

# ---------------------------------------------------------------------------
# t14: session-init.sh does NOT overwrite existing .rabbit-prompt-counter
# ---------------------------------------------------------------------------
echo "=== t14: session-init.sh does NOT overwrite existing .rabbit-prompt-counter ==="

TMPROOT_MIGRATE3=""
TMPROOT_MIGRATE3="$(mktemp -d)"
git init -q "$TMPROOT_MIGRATE3"
git -C "$TMPROOT_MIGRATE3" config user.email "test@test.com"
git -C "$TMPROOT_MIGRATE3" config user.name "Test"
git -C "$TMPROOT_MIGRATE3" checkout -q -b main 2>/dev/null || true

mkdir -p "$TMPROOT_MIGRATE3/.claude/features/rabbit-cage/scripts"
mkdir -p "$TMPROOT_MIGRATE3/.claude/features/policy"

printf '# Philosophy\nMachine First.\n'   > "$TMPROOT_MIGRATE3/.claude/features/policy/philosophy.md"
printf '# Spec Rules\nSpec.\n'            > "$TMPROOT_MIGRATE3/.claude/features/policy/spec-rules.md"
printf '# Coding Rules\nCode.\n'          > "$TMPROOT_MIGRATE3/.claude/features/policy/coding-rules.md"
printf '# Workflow Rules\nWorkflow.\n'    > "$TMPROOT_MIGRATE3/.claude/features/policy/workflow-rules.md"

python3 -c "import json; print(json.dumps({'header': '# Rabbit Workflow — test header'}))" \
    > "$TMPROOT_MIGRATE3/.claude/features/rabbit-cage/policy-header.json"

cp "$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" \
   "$TMPROOT_MIGRATE3/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

python3 -c "import json; print(json.dumps({'schema_version':'1.0.0','features':{}}))" \
    > "$TMPROOT_MIGRATE3/.claude/features/registry.json"

CORRECT3="$(RABBIT_ROOT="$TMPROOT_MIGRATE3" bash "$TMPROOT_MIGRATE3/.claude/features/rabbit-cage/scripts/generate-claude-md.sh" 2>/dev/null)"
printf '%s\n' "$CORRECT3" > "$TMPROOT_MIGRATE3/CLAUDE.md"

git -C "$TMPROOT_MIGRATE3" add -A
git -C "$TMPROOT_MIGRATE3" commit -q -m "init"

# Both files exist — new one should win (not be overwritten by migration)
printf '99\n' > "$TMPROOT_MIGRATE3/.rabbit-prompt-counter"
printf '5\n' > "$TMPROOT_MIGRATE3/.rbt-prompt-counter"

# Run session-init.sh
RABBIT_ROOT="$TMPROOT_MIGRATE3" bash "$SESSION_INIT" >/dev/null 2>&1 || true

EXISTING_VAL="$(cat "$TMPROOT_MIGRATE3/.rabbit-prompt-counter" 2>/dev/null || echo '')"
if printf '%s' "$EXISTING_VAL" | grep -qx '0\|99' 2>/dev/null; then
    # session-init resets to 0 normally, so 0 is also valid; 99 means it wasn't clobbered
    ok "session-init.sh did not destroy existing .rabbit-prompt-counter with legacy migration"
else
    fail_t "session-init.sh may have incorrectly overwritten existing .rabbit-prompt-counter (value: $EXISTING_VAL)"
fi

rm -rf "$TMPROOT_MIGRATE3"

# ---------------------------------------------------------------------------
# t15: deployed .claude/hooks/refresh.sh uses new names (not rbt-)
# ---------------------------------------------------------------------------
echo "=== t15: deployed refresh.sh uses new names ==="

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
# t16: deployed .claude/hooks/sync-check.sh uses new names (not rbt-)
# ---------------------------------------------------------------------------
echo "=== t16: deployed sync-check.sh uses new names ==="

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
# t17: deployed .claude/settings.json uses new names (not rbt-)
# ---------------------------------------------------------------------------
echo "=== t17: deployed settings.json uses new names ==="

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
