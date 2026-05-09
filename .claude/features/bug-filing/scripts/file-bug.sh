#!/bin/bash
# file-bug.sh — file a new bug under $BUG_ROOT (default: .claude/docs/bugs).
#
# Usage:
#   file-bug.sh --title <t> --severity <l|m|h|c> --description <d>
#               [--related-feature <name>] [--filed-by <actor>]
#
# Bug ID: <PREFIX>-<N>
#   PREFIX = related_feature uppercased (e.g. "worklog" -> "WORKLOG")
#            or $BUG_PREFIX env var (default: RBT) when --related-feature omitted.
#   N      = max existing N for this prefix in $BUG_ROOT + 1. No padding. No ceiling.
#
# Severity:  low | medium | high | critical
# Status:    always seeded as 'open'
#
# Exit: 0 success; 1 validation error; 2 invocation error.

set -u

BUG_ROOT="${BUG_ROOT:-.claude/docs/bugs}"
BUG_PREFIX="${BUG_PREFIX:-RBT}"

usage() {
  cat >&2 <<EOF
usage: file-bug.sh --title T --severity {low|medium|high|critical} \\
                   --description D [--related-feature F] [--filed-by A]
EOF
}

TITLE=""; SEV=""; DESC=""; FEAT=""; FILER=""

while [ $# -gt 0 ]; do
  case "$1" in
    --title)             TITLE="$2"; shift 2 ;;
    --severity)          SEV="$2"; shift 2 ;;
    --description)       DESC="$2"; shift 2 ;;
    --related-feature)   FEAT="$2"; shift 2 ;;
    --filed-by)          FILER="$2"; shift 2 ;;
    -h|--help)           usage; exit 0 ;;
    *)                   echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

[ -z "$TITLE" ] && { echo "ERROR: --title required" >&2; exit 1; }
[ -z "$SEV" ]   && { echo "ERROR: --severity required" >&2; exit 1; }
[ -z "$DESC" ]  && { echo "ERROR: --description required" >&2; exit 1; }

case "$SEV" in
  low|medium|high|critical) ;;
  *) echo "ERROR: invalid severity '$SEV' (allowed: low|medium|high|critical)" >&2; exit 1 ;;
esac

if [ -n "$FEAT" ]; then
  if ! echo "$FEAT" | grep -qE '^[a-z][a-z0-9-]{0,49}$'; then
    echo "ERROR: --related-feature '$FEAT' must match [a-z][a-z0-9-]* (max 50 chars)" >&2
    exit 1
  fi
fi

# Derive prefix: related-feature uppercased, or $BUG_PREFIX fallback.
if [ -n "$FEAT" ]; then
  PREFIX="$(echo "$FEAT" | tr '[:lower:]' '[:upper:]')"
else
  PREFIX="$BUG_PREFIX"
fi

# Scan BUG_ROOT for existing IDs with this prefix, find max N.
MAX=0
if [ -d "$BUG_ROOT" ]; then
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    existing_name="$(jq -r '.name // ""' "$f" 2>/dev/null)"
    if echo "$existing_name" | grep -qE "^${PREFIX}-([1-9][0-9]*)$"; then
      n="$(echo "$existing_name" | sed -E "s/^${PREFIX}-//")"
      [ "$n" -gt "$MAX" ] 2>/dev/null && MAX="$n"
    fi
  done < <(find "$BUG_ROOT" -name "bug.json" -maxdepth 2)
fi
N=$((MAX + 1))
NAME="${PREFIX}-${N}"

BUG_DIR="$BUG_ROOT/$NAME"
if [ -e "$BUG_DIR" ]; then
  echo "ERROR: bug '$NAME' already exists at $BUG_DIR" >&2
  exit 1
fi

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

echo "filed: $BUG_DIR/bug.json  [$NAME]"
exit 0
