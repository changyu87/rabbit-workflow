#!/usr/bin/env bash
# file-backlog-item.sh — file a new backlog item under <feature-dir>/docs/backlog/.
#
# Usage:
#   file-backlog-item.sh <feature-dir> <item-id> <title> \
#                        [--priority low|medium|high|critical] [--owner <name>]
#
# Positional args:
#   <feature-dir>  path to the feature directory (e.g. .claude/features/rabbit-cage)
#   <item-id>      item identifier (e.g. BACKLOG-001)
#   <title>        short human-readable title
#
# Options:
#   --priority    low | medium | high | critical (default: medium)
#   --owner       owner name (default: $USER or "unknown")
#
# Creates: <feature-dir>/docs/backlog/<item-id>/item.json
# Prints:  the created item directory path to stdout
# Exit:    0=created  1=error  2=usage

set -u

usage() {
  cat >&2 <<EOF
usage: file-backlog-item.sh <feature-dir> <item-id> <title> \\
                             [--priority low|medium|high|critical] [--owner <name>]
EOF
}

# Require at least 3 positional args
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage; exit 0
fi

if [ $# -lt 3 ]; then
  usage; exit 2
fi

FEATURE_DIR="$1"
ITEM_ID="$2"
TITLE="$3"
shift 3

PRIORITY="medium"
OWNER="${USER:-unknown}"

while [ $# -gt 0 ]; do
  case "$1" in
    --priority) PRIORITY="$2"; shift 2 ;;
    --owner)    OWNER="$2";    shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *)          echo "ERROR: unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

# Validate feature-dir
if [ ! -d "$FEATURE_DIR" ]; then
  echo "ERROR: feature-dir does not exist: $FEATURE_DIR" >&2
  exit 1
fi

# Validate item-id (must be non-empty)
if [ -z "$ITEM_ID" ]; then
  echo "ERROR: item-id must be non-empty" >&2
  exit 1
fi

# Validate priority
case "$PRIORITY" in
  low|medium|high|critical) ;;
  *) echo "ERROR: invalid priority '$PRIORITY' (allowed: low|medium|high|critical)" >&2; exit 1 ;;
esac

BACKLOG_ROOT="$FEATURE_DIR/docs/backlog"
ITEM_DIR="$BACKLOG_ROOT/$ITEM_ID"

if [ -e "$ITEM_DIR" ]; then
  echo "ERROR: item '$ITEM_ID' already exists at $ITEM_DIR" >&2
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
