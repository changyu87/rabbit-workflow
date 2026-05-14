#!/usr/bin/env bash
# build.sh — unified workspace artifact builder.
#
# Reads .claude/features/contract/build-contract.json and builds all declared targets.
# Usage: build.sh [REPO_ROOT]
#
# Version: 1.0.0
# Owner: rabbit-workflow team (rabbit-cage)
# Deprecation criterion: when Claude Code natively manages workspace artifact generation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
CONTRACT="$REPO_ROOT/.claude/features/contract/build-contract.json"
GENERATE_CLAUDE_MD="$REPO_ROOT/.claude/features/rabbit-cage/scripts/generate-claude-md.sh"

[ -f "$CONTRACT" ] || { echo "build: contract not found: $CONTRACT" >&2; exit 1; }

# Pass RABBIT_ROOT so generate-claude-md.sh works in non-git directories (invariant 30)
RABBIT_ROOT="$REPO_ROOT" python3 "$SCRIPT_DIR/build-targets.py" "$REPO_ROOT" "$CONTRACT" "$GENERATE_CLAUDE_MD"
