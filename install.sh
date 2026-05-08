#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-$PWD}"

if [[ -d "$TARGET/.claude" ]]; then
    echo "Error: $TARGET/.claude already exists." >&2
    echo "If developing rabbit-workflow, no install needed — open this directory in Claude Code." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.claude" ]]; then
    cp -r "$SCRIPT_DIR/.claude" "$TARGET/.claude"
    cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"
else
    TMP="$(mktemp -d)"
    trap "rm -rf '$TMP'" EXIT
    curl -fsSL https://github.com/USER/rabbit-workflow/archive/refs/heads/main.tar.gz \
        | tar -xz -C "$TMP" --strip-components=1
    cp -r "$TMP/.claude" "$TARGET/.claude"
    cp "$TMP/CLAUDE.md" "$TARGET/CLAUDE.md"
fi

chmod +x "$TARGET/.claude/hooks/rwf-refresh.sh"
echo "rabbit-workflow installed to $TARGET"
