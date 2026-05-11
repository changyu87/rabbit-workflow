#!/bin/bash
# audit-orphan-storage.sh — scan .claude/bugs/ and .claude/backlogs/ for
# subdirectory names not present in registry.json features; alert on orphans.
#
# Usage: audit-orphan-storage.sh [--bugs-root DIR] [--backlogs-root DIR] [--registry FILE]
#
# Exit codes:
#   0  no orphans found
#   1  one or more orphans found

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

ORPHAN_FOUND=0

# Read all feature names from registry.json
if [ ! -f "$REGISTRY" ]; then
  echo "ERROR: registry not found: $REGISTRY" >&2
  exit 1
fi

KNOWN_FEATURES="$(python3 -c "
import json, sys
r = json.load(open('$REGISTRY'))
for name in r.get('features', {}).keys():
    print(name)
")"

check_dir() {
  local root="$1"
  local label="$2"
  if [ ! -d "$root" ]; then
    echo "INFO  ${label}/ (directory does not exist)"
    return
  fi
  for subdir in "$root"/*/; do
    [ -d "$subdir" ] || continue
    name="$(basename "$subdir")"
    if ! echo "$KNOWN_FEATURES" | grep -qx "$name"; then
      echo "ORPHAN  ${label}/${name}/"
      ORPHAN_FOUND=1
    fi
  done
}

check_dir "$BUGS_ROOT"     "bugs"
check_dir "$BACKLOGS_ROOT" "backlogs"

# Report known features with no bugs subdir
while IFS= read -r feature; do
  [ -z "$feature" ] && continue
  if [ ! -d "$BUGS_ROOT/$feature" ]; then
    echo "INFO  bugs/${feature}/ (never filed)"
  fi
done <<< "$KNOWN_FEATURES"

exit $ORPHAN_FOUND
