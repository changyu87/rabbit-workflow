#!/usr/bin/env bash
# rwf-refresh.sh — periodic re-injection of CLAUDE.md @-imports.
#
# Wired to UserPromptSubmit. Each prompt: increment counter; if counter
# reaches RWF_REFRESH_EVERY (default 10), emit JSON additionalContext
# containing the full content of every file that CLAUDE.md @-imports,
# then reset the counter to 0.
#
# Stays silent (exits 0 with no stdout) when not refreshing.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
COUNTER_FILE="$REPO_ROOT/.rwf-counter"
THRESHOLD="${RWF_REFRESH_EVERY:-10}"

# Initialize counter on first run
[ -f "$COUNTER_FILE" ] || echo 0 > "$COUNTER_FILE"

count=$(cat "$COUNTER_FILE")
count=$((count + 1))

if [ "$count" -lt "$THRESHOLD" ]; then
    echo "$count" > "$COUNTER_FILE"
    exit 0
fi

# Threshold reached: gather @-imports from CLAUDE.md, emit additionalContext
echo 0 > "$COUNTER_FILE"

# Parse lines like '@./foo.md' or '@/abs/path.md' from CLAUDE.md
imports=$(grep -oE '^@[^[:space:]]+' "$CLAUDE_MD" | sed 's/^@//' || true)

if [ -z "$imports" ]; then
    exit 0
fi

# Build the injected context
payload_file="$(mktemp)"
trap 'rm -f "$payload_file"' EXIT

{
    printf 'Periodic policy refresh (every %s prompts). Re-stating governing files:\n\n' "$THRESHOLD"
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

# Emit JSON for Claude Code: additionalContext is read from stdout
python3 -c "
import json
with open('$payload_file', 'r') as f:
    payload = f.read()
print(json.dumps({'additionalContext': payload}))
"
