#!/bin/bash
# audit-orphan-storage.sh — scan .claude/bugs/ and .claude/backlogs/ for
# subdirectory names not present in registry.json features; alert on orphans.
#
# Usage: audit-orphan-storage.sh [--bugs-root DIR] [--backlogs-root DIR] [--registry FILE]
#
# Exit codes:
#   0  no orphans found
#   1  one or more orphans found
#
# Version: 1.1.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when feature registry lookup is natively provided.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")"

BUGS_ROOT="${REPO_ROOT}/.claude/bugs"
BACKLOGS_ROOT="${REPO_ROOT}/.claude/backlogs"
REGISTRY="${REPO_ROOT}/.claude/features/registry.json"

# Parse optional arguments
while [ $# -gt 0 ]; do
  case "$1" in
    --bugs-root)     BUGS_ROOT="$2";    shift 2 ;;
    --backlogs-root) BACKLOGS_ROOT="$2"; shift 2 ;;
    --registry)      REGISTRY="$2";    shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ ! -f "$REGISTRY" ]; then
  echo "ERROR: registry not found: $REGISTRY" >&2
  exit 1
fi

python3 "$SCRIPT_DIR/audit-orphan-storage.py" "$REGISTRY" "$BUGS_ROOT" "$BACKLOGS_ROOT"
