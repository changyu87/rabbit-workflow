#!/usr/bin/env bash
# rbt-session-init.sh — session-start injection of CLAUDE.md @-imports.
#
# Wired to SessionStart. Fires immediately at session start (no counter gate).
# Reads all @-import paths from CLAUDE.md and emits them as additionalContext
# JSON so policy is present from the very first prompt.
#
# Output format: {"additionalContext": "...", "systemMessage": "..."}
# Stays silent (exits 0 with no stdout) if no @-imports found in CLAUDE.md.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively injects CLAUDE.md @-imports at session start.

set -euo pipefail

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)}"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"

# Ensure .claude/skills/ is generated and hash baseline is saved.
_GENERATE_SKILLS="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-skills-dir.sh"
[ -f "$_GENERATE_SKILLS" ] && bash "$_GENERATE_SKILLS" "$REPO_ROOT" >/dev/null 2>&1 || true

# Try to read inline policy section between rabbit-policy-start and rabbit-policy-end markers
INLINE=$(sed -n '/rabbit-policy-start/,/rabbit-policy-end/p' "$CLAUDE_MD" 2>/dev/null | grep -v 'rabbit-policy-start\|rabbit-policy-end' || true)

if [ -n "$INLINE" ]; then
    # Inline section found: inject it as additionalContext
    python3 -c "
import json, sys
payload = sys.stdin.read()
print(json.dumps({
    'additionalContext': payload,
    'systemMessage': '✅ ━━━ [rabbit] Policy injected at session start (inline section from CLAUDE.md) ━━━ ✅'
}))
" <<< "$INLINE"
    exit 0
fi

# Fallback: parse lines like '@./foo.md' or '@/abs/path.md' from CLAUDE.md
imports=$(grep -oE '^@[^[:space:]]+' "$CLAUDE_MD" | sed 's/^@//' || true)

if [ -z "$imports" ]; then
    exit 0
fi

# Build the injected context
payload_file="$(mktemp)"
trap 'rm -f "$payload_file"' EXIT

{
    printf 'Session start policy injection. Governing files from CLAUDE.md @-imports:\n\n'
    while IFS= read -r path; do
        # Resolve relative paths against repo root
        case "$path" in
            /*) full="$path" ;;
            *)  full="$REPO_ROOT/${path#./}" ;;
        esac
        if [ -f "$full" ]; then
            printf -- '--- %s ---\n' "$path"
            cat "$full"
            printf '\n'
        fi
    done <<< "$imports"
} > "$payload_file"

# Emit JSON for Claude Code: additionalContext (Claude-visible) + systemMessage (user-visible)
files_label=$(echo "$imports" | tr '\n' ' ')
python3 -c "
import json
with open('$payload_file', 'r') as f:
    payload = f.read()
print(json.dumps({
    'additionalContext': payload,
    'systemMessage': '✅ ━━━ [rabbit] Policy injected at session start — $files_label ━━━ ✅'
}))
"
