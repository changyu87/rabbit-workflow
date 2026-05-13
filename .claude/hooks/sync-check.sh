#!/usr/bin/env bash
# sync-check.sh — Stop hook: detect policy drift in CLAUDE.md and regenerate.
#
# Fires on Stop event. Compares the inline policy section of CLAUDE.md against
# the current policy source files. If drift detected: regenerates CLAUDE.md,
# emits additionalContext with the refreshed policy, and alerts the user.
#
# Counter-gated: only checks every RBT_SYNC_EVERY stops (default 1).
# Override in .claude/settings.local.json: {"env": {"RBT_SYNC_EVERY": "5"}}
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively resolves @-imports for subagents.

set -euo pipefail

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
GENERATE_SCRIPT="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"
COUNTER_FILE="$REPO_ROOT/.rbt-sync-counter"
THRESHOLD="${RBT_SYNC_EVERY:-1}"

# Initialize counter
[ -f "$COUNTER_FILE" ] || echo 0 > "$COUNTER_FILE"
count=$(cat "$COUNTER_FILE")
count=$((count + 1))
if [ "$count" -lt "$THRESHOLD" ]; then
  echo "$count" > "$COUNTER_FILE"
  exit 0
fi
echo 0 > "$COUNTER_FILE"

# Generate expected content
EXPECTED="$(bash "$GENERATE_SCRIPT" 2>/dev/null)" || exit 0

# If CLAUDE.md does not exist: first-run scenario — create it with first-run message.
if [ ! -f "$CLAUDE_MD" ]; then
  printf '%s\n' "$EXPECTED" > "$CLAUDE_MD"
  echo "${RBT_REFRESH_EVERY:-20}" > "${REPO_ROOT}/.rbt-prompt-counter"
  POLICY_SECTION="$(printf '%s\n' "$EXPECTED" | sed -n '/rabbit-policy-start/,/rabbit-policy-end/p')"
  python3 -c "
import json, sys
payload = sys.stdin.read()
print(json.dumps({
    'additionalContext': payload,
    'systemMessage': '\x1b[32m📋 ━━━ [rabbit] Policy initialized — CLAUDE.md created for first time ━━━ 📋\x1b[0m'
}))
" <<< "$POLICY_SECTION"
  exit 0
fi

# If CLAUDE.md exists but differs from expected: genuine drift — regenerate and alert.
if [ "$(cat "$CLAUDE_MD")" != "$EXPECTED" ]; then
  printf '%s\n' "$EXPECTED" > "$CLAUDE_MD"
  echo "${RBT_REFRESH_EVERY:-20}" > "${REPO_ROOT}/.rbt-prompt-counter"
  POLICY_SECTION="$(printf '%s\n' "$EXPECTED" | sed -n '/rabbit-policy-start/,/rabbit-policy-end/p')"
  python3 -c "
import json, sys
payload = sys.stdin.read()
print(json.dumps({
    'additionalContext': payload,
    'systemMessage': '\x1b[31m⚠️ ━━━ [rabbit] Policy drift detected — CLAUDE.md regenerated from source files ━━━ ⚠️\x1b[0m'
}))
" <<< "$POLICY_SECTION"
  exit 0
fi

# Track whether any JSON was emitted below (single-JSON-per-invocation invariant).
_json_emitted=0

# Surface drift check — only reached when CLAUDE.md is clean (no double JSON output).
_TEST_SURFACE="$REPO_ROOT/.claude/features/rabbit-cage/test/test-generated-surface.sh"
_BUILD="$REPO_ROOT/.claude/features/rabbit-cage/scripts/build.sh"
if [ -f "$_TEST_SURFACE" ] && ! bash "$_TEST_SURFACE" >/dev/null 2>&1; then
  bash "$_BUILD" "$REPO_ROOT" >/dev/null 2>&1 || true
  python3 -c "
import json
print(json.dumps({
    'systemMessage': '\x1b[32m🔄 ━━━ [rabbit] Surface drift detected — workspace rebuilt from sources ━━━ 🔄\x1b[0m'
}))
"
  _json_emitted=1
fi

# Override alert — fires when guard was bypassed this session
OVERRIDE_FILE="${REPO_ROOT}/.rabbit-scope-override"
USED_FILE="${REPO_ROOT}/.rabbit-scope-override-used"

_alert=""
if [ -f "$OVERRIDE_FILE" ]; then
  _mode="$(cat "$OVERRIDE_FILE" | tr -d '[:space:]')"
  if [ "$_mode" = "session" ]; then
    _alert="session"
  fi
fi
if [ -f "$USED_FILE" ]; then
  _alert="used"
  rm -f "$USED_FILE"
fi

if [ "$_json_emitted" -eq 0 ]; then
  if [ "$_alert" = "session" ]; then
    python3 -c "
import json
print(json.dumps({
    'systemMessage': '\x1b[31m\xf0\x9f\x94\x93 \xe2\x94\x81\xe2\x94\x81\xe2\x94\x81 [rabbit] SCOPE GUARD OFF (session override active) \xe2\x94\x81\xe2\x94\x81\xe2\x94\x81 \xf0\x9f\x94\x93\x1b[0m'
}))
"
    _json_emitted=1
  elif [ "$_alert" = "used" ]; then
    python3 -c "
import json
print(json.dumps({
    'systemMessage': '\x1b[31m🔓 ━━━ [rabbit] SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed) ━━━ 🔓\x1b[0m'
}))
"
    _json_emitted=1
  fi
fi

# Plugin-change detection — detects any changes to plugin dirs since session branch-point.
# Emits green [rabbit] alert listing changed files and instructing /reload-plugins.
# Only fires if no prior check emitted JSON (single-JSON-per-invocation invariant).
if [ "$_json_emitted" -eq 0 ]; then
  _BASE=""
  if git -C "$REPO_ROOT" rev-parse main >/dev/null 2>&1; then
    _BASE="$(git -C "$REPO_ROOT" merge-base HEAD main 2>/dev/null)" || true
  fi
  if [ -z "$_BASE" ] && git -C "$REPO_ROOT" rev-parse origin/main >/dev/null 2>&1; then
    _BASE="$(git -C "$REPO_ROOT" merge-base HEAD origin/main 2>/dev/null)" || true
  fi
  if [ -n "$_BASE" ]; then
    _CHANGED="$(git -C "$REPO_ROOT" diff --name-only "$_BASE" HEAD -- .claude/skills/ .claude/commands/ .claude/agents/ 2>/dev/null)" || true
    if [ -n "$_CHANGED" ]; then
      _FILE_LIST="$(printf '%s' "$_CHANGED" | python3 -c "import sys; files=sys.stdin.read().strip().splitlines(); print('\n'.join('  • ' + f for f in files))")"
      python3 -c "
import json, os
file_list = os.environ.get('_FILE_LIST', '')
msg = '\x1b[32m[rabbit] Plugins updated this session \xe2\x80\x94 run /reload-plugins to load the latest skills/commands into Claude.\x1b[0m'
if file_list:
    msg += '\nChanged files:\n' + file_list
print(json.dumps({'systemMessage': msg}))
" _FILE_LIST="$_FILE_LIST"
    fi
  fi
fi

exit 0
