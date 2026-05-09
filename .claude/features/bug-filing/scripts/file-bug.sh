#!/bin/bash
# file-bug.sh — create a new bug under $BUG_ROOT (default: .claude/docs/bugs).
#
# Usage:
#   file-bug.sh --name <YYYY-MM-DD-slug> --title <t> --severity <l|m|h|c> --description <d>
#               [--related-feature <name>] [--filed-by <actor>]
#
# Naming rule: ^\d{4}-\d{2}-\d{2}-[a-z][a-z0-9-]{0,49}$  (max 61 chars total)
# Severity:    low | medium | high | critical
# Status:      always seeded as 'open'
#
# Exit: 0 success; 1 validation error; 2 invocation error.

set -u

BUG_ROOT="${BUG_ROOT:-.claude/docs/bugs}"

usage() {
  cat >&2 <<EOF
usage: file-bug.sh --name N --title T --severity {low|medium|high|critical} \\
                   --description D [--related-feature F] [--filed-by A]
EOF
}

NAME=""; TITLE=""; SEV=""; DESC=""; FEAT=""; FILER=""

while [ $# -gt 0 ]; do
  case "$1" in
    --name)              NAME="$2"; shift 2 ;;
    --title)             TITLE="$2"; shift 2 ;;
    --severity)          SEV="$2"; shift 2 ;;
    --description)       DESC="$2"; shift 2 ;;
    --related-feature)   FEAT="$2"; shift 2 ;;
    --filed-by)          FILER="$2"; shift 2 ;;
    -h|--help)           usage; exit 0 ;;
    *)                   echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

[ -z "$NAME" ]  && { echo "ERROR: --name required" >&2; exit 1; }
[ -z "$TITLE" ] && { echo "ERROR: --title required" >&2; exit 1; }
[ -z "$SEV" ]   && { echo "ERROR: --severity required" >&2; exit 1; }
[ -z "$DESC" ]  && { echo "ERROR: --description required" >&2; exit 1; }

# Validate name format
if ! echo "$NAME" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z][a-z0-9-]{0,49}$'; then
  echo "ERROR: bug name '$NAME' violates rule (YYYY-MM-DD-<lowercase-slug>, max 61 chars)" >&2
  exit 1
fi

# Validate severity
case "$SEV" in
  low|medium|high|critical) ;;
  *) echo "ERROR: invalid severity '$SEV' (allowed: low|medium|high|critical)" >&2; exit 1 ;;
esac

# Dedup
BUG_DIR="$BUG_ROOT/$NAME"
if [ -e "$BUG_DIR" ]; then
  echo "ERROR: bug name '$NAME' already exists at $BUG_DIR" >&2
  exit 1
fi

# Default filer
[ -z "$FILER" ] && FILER="${USER:-unknown}"

mkdir -p "$BUG_DIR"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

jq -n \
  --arg name "$NAME" \
  --arg title "$TITLE" \
  --arg sev "$SEV" \
  --arg desc "$DESC" \
  --arg feat "$FEAT" \
  --arg filer "$FILER" \
  --arg ts "$TS" \
  '{
    name: $name,
    title: $title,
    status: "open",
    severity: $sev,
    description: $desc,
    related_feature: (if $feat == "" then null else $feat end),
    filed: $ts,
    filed_by: $filer,
    closed: null,
    closed_by: null,
    history: [
      { ts: $ts, actor: $filer, action: "opened", note: "initial filing" }
    ]
  }' > "$BUG_DIR/bug.json"

echo "filed: $BUG_DIR/bug.json"
exit 0
