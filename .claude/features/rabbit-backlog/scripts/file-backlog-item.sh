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

REPO_ROOT="${RABBIT_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}"
FIND_FEATURE="$REPO_ROOT/.claude/features/contract/scripts/find-feature.sh"

# Validate feature exists via find-feature.sh
bash "$FIND_FEATURE" "$FEATURE_NAME" >/dev/null 2>&1 || {
  echo "ERROR: feature '$FEATURE_NAME' not found in feature index" >&2
  exit 1
}

# Build prefix: rabbit-cage → RABBIT-CAGE, rabbit-backlog → RABBIT-BACKLOG
PREFIX="$(echo "$FEATURE_NAME" | tr '[:lower:]' '[:upper:]')"

# Resolve canonical backlog storage path via workspace-map.sh (contract).
# workspace-map.sh is located at .claude/features/contract/scripts/workspace-map.sh
# and may also be found via PATH if injected by callers or tests.
_WORKSPACE_MAP="$(command -v workspace-map.sh 2>/dev/null || echo "$REPO_ROOT/.claude/features/contract/scripts/workspace-map.sh")"
if [ ! -x "$_WORKSPACE_MAP" ]; then
  echo "ERROR: workspace-map.sh not found or not executable: $_WORKSPACE_MAP" >&2
  exit 1
fi
BACKLOG_ROOT="$(RABBIT_ROOT="$REPO_ROOT" "$_WORKSPACE_MAP" backlog "$FEATURE_NAME")" || {
  echo "ERROR: workspace-map.sh failed to resolve path for feature '$FEATURE_NAME'" >&2
  exit 1
}
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

# Git commit after filing — silent on failure
REPO_ROOT="$(git -C "$ITEM_DIR" rev-parse --show-toplevel 2>/dev/null)" || true
if [ -n "$REPO_ROOT" ]; then
  git -C "$REPO_ROOT" add "$ITEM_DIR/item.json" 2>/dev/null && \
    git -C "$REPO_ROOT" commit -m "backlog: file $ITEM_ID ($TITLE)" 2>/dev/null || true
fi

echo "$ITEM_DIR"
exit 0
