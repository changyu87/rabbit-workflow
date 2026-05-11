#!/usr/bin/env bash
# file-backlog-item.sh — file a new backlog item in centralized storage.
#
# Usage:
#   file-backlog-item.sh --related-feature <name> --title <title> \
#                        [--priority low|medium|high|critical] \
#                        [--owner <name>]
#
# Options:
#   --related-feature  feature name (must exist in registry.json)
#   --title            short human-readable title
#   --priority         low | medium | high | critical (default: medium)
#   --owner            owner name (default: $USER or "unknown")
#
# Creates: .claude/backlogs/<feature-name>/<PREFIX>-BACKLOG-<N>/item.json
# Prints:  the created item directory path to stdout
# Exit:    0=created  1=error  2=usage

set -u

usage() {
  cat >&2 <<EOF
usage: file-backlog-item.sh --related-feature <name> --title <title> \\
                             [--priority low|medium|high|critical] \\
                             [--owner <name>]
EOF
}

FEATURE_NAME=""
TITLE=""
PRIORITY="medium"
OWNER="${USER:-unknown}"

while [ $# -gt 0 ]; do
  case "$1" in
    --related-feature) FEATURE_NAME="$2"; shift 2 ;;
    --title)           TITLE="$2";         shift 2 ;;
    --priority)        PRIORITY="$2";      shift 2 ;;
    --owner)           OWNER="$2";         shift 2 ;;
    -h|--help)         usage; exit 0 ;;
    *)                 echo "ERROR: unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [ -z "$FEATURE_NAME" ] || [ -z "$TITLE" ]; then
  echo "ERROR: --related-feature and --title are required" >&2
  usage; exit 2
fi

# Validate priority
case "$PRIORITY" in
  low|medium|high|critical) ;;
  *) echo "ERROR: invalid priority '$PRIORITY' (allowed: low|medium|high|critical)" >&2; exit 1 ;;
esac

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
REGISTRY="$REPO_ROOT/.claude/features/registry.json"

# Validate feature exists in registry
if ! jq -e --arg f "$FEATURE_NAME" '.features[$f]' "$REGISTRY" > /dev/null 2>&1; then
  echo "ERROR: feature '$FEATURE_NAME' not found in registry.json" >&2
  exit 1
fi

# Build prefix: rabbit-cage → RABBIT-CAGE, rabbit-backlog → RABBIT-BACKLOG
PREFIX="$(echo "$FEATURE_NAME" | tr '[:lower:]' '[:upper:]')"

BACKLOG_ROOT="$REPO_ROOT/.claude/backlogs/$FEATURE_NAME"
mkdir -p "$BACKLOG_ROOT"

# Scan for existing items matching PREFIX-BACKLOG-<N>, find max N
MAX=0
if [ -d "$BACKLOG_ROOT" ]; then
  for d in "$BACKLOG_ROOT"/${PREFIX}-BACKLOG-*/; do
    [ -d "$d" ] || continue
    base="$(basename "$d")"
    n="${base##*-}"
    case "$n" in
      ''|*[!0-9]*) continue ;;
    esac
    [ "$n" -gt "$MAX" ] && MAX="$n"
  done
fi

ITEM_NUM=$(( MAX + 1 ))
ITEM_ID="${PREFIX}-BACKLOG-${ITEM_NUM}"
ITEM_DIR="$BACKLOG_ROOT/$ITEM_ID"

if [ -e "$ITEM_DIR/item.json" ]; then
  echo "ERROR: item.json already exists at $ITEM_DIR" >&2
  exit 1
fi

mkdir -p "$ITEM_DIR" || { echo "ERROR: failed to create $ITEM_DIR" >&2; exit 1; }

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

jq -n \
  --arg name     "$ITEM_ID" \
  --arg title    "$TITLE" \
  --arg priority "$PRIORITY" \
  --arg owner    "$OWNER" \
  --arg filed_by "$OWNER" \
  --arg ts       "$TS" \
  '{
    name:        $name,
    title:       $title,
    status:      "open",
    priority:    $priority,
    description: "",
    owner:       $owner,
    filed:       $ts,
    filed_by:    $filed_by,
    closed:      null,
    history: [
      { ts: $ts, actor: $filed_by, action: "opened", note: "initial filing" }
    ]
  }' > "$ITEM_DIR/item.json" || { echo "ERROR: failed to write item.json" >&2; exit 1; }

echo "$ITEM_DIR"
exit 0
