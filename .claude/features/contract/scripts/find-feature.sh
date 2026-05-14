#!/bin/bash
# find-feature.sh — distributed feature registry lookup.
# Replaces registry.json as the authoritative feature index.
#
# Usage:
#   find-feature.sh <feature-name>   # print relative path to feature dir; exit 1 if not found
#   find-feature.sh --list            # print all feature names, one per line
#   find-feature.sh --list-json       # print [{name,path,summary,tdd_state},...] as JSON
#
# Version: 1.1.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when feature discovery is handled natively by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$REPO_ROOT" ] && { echo "ERROR: cannot determine repo root" >&2; exit 1; }

CMD="${1:-}"

case "$CMD" in
  --list)
    python3 "$SCRIPT_DIR/find-feature.py" "$REPO_ROOT" list
    exit $?
    ;;

  --list-json)
    python3 "$SCRIPT_DIR/find-feature.py" "$REPO_ROOT" list-json
    exit $?
    ;;

  ""|--help|-h)
    echo "usage: find-feature.sh <feature-name> | --list | --list-json" >&2
    exit 2
    ;;

  -*)
    echo "ERROR: unknown option '$CMD'" >&2
    exit 2
    ;;

  *)
    FEATURE_NAME="$CMD"
    result=$(python3 "$SCRIPT_DIR/find-feature.py" "$REPO_ROOT" lookup "$FEATURE_NAME")
    status=$?
    if [ $status -ne 0 ] || [ -z "$result" ]; then
      echo "ERROR: feature '$FEATURE_NAME' not found" >&2
      exit 1
    fi
    echo "$result"
    ;;
esac
