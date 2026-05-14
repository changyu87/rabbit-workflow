#!/usr/bin/env bash
# workspace-tree.sh — print annotated workspace hierarchy
# Usage:
#   workspace-tree.sh          # structural view (dirs + key files only)
#   workspace-tree.sh --full   # all files (excl .swp, .git/*, .rabbit-prompt-counter)
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
FULL=0
[ "${1:-}" = "--full" ] && FULL=1

python3 "$SCRIPT_DIR/workspace-tree.py" "$REPO_ROOT" "$FULL"
