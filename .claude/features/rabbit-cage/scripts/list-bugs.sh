#!/bin/bash
# list-bugs.sh — list bugs under $BUG_ROOT (default: .claude/docs/bugs).
#
# Usage:
#   list-bugs.sh                          # JSON array of all bugs
#   list-bugs.sh --status <s>             # filter by status
#   list-bugs.sh --feature <name>         # filter by related_feature
#   list-bugs.sh --status s --feature f   # combine filters
#   list-bugs.sh --text                   # human-readable text instead of JSON
#
# Exit: 0 on success.

set -u

BUG_ROOT="${BUG_ROOT:-.claude/docs/bugs}"

mode="json"
filter_status=""
filter_feature=""

while [ $# -gt 0 ]; do
  case "$1" in
    --status)  filter_status="$2"; shift 2 ;;
    --feature) filter_feature="$2"; shift 2 ;;
    --text)    mode="text"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Empty / missing root → empty list
if [ ! -d "$BUG_ROOT" ] || [ -z "$(ls -A "$BUG_ROOT" 2>/dev/null)" ]; then
  if [ "$mode" = "text" ]; then
    echo "(no bugs)"
  else
    echo "[]"
  fi
  exit 0
fi

# Collect all bug.json files
files=()
for d in "$BUG_ROOT"/*/; do
  [ -f "$d/bug.json" ] && files+=("$d/bug.json")
done

if [ "${#files[@]}" -eq 0 ]; then
  if [ "$mode" = "text" ]; then echo "(no bugs)"; else echo "[]"; fi
  exit 0
fi

# Build a JSON array, optionally filtered.
JQ_FILTER="."
if [ -n "$filter_status" ]; then
  JQ_FILTER="$JQ_FILTER | select(.status == \"$filter_status\")"
fi
if [ -n "$filter_feature" ]; then
  JQ_FILTER="$JQ_FILTER | select(.related_feature == \"$filter_feature\")"
fi

# Slurp all bug.json files into an array, apply filter, output.
JSON_ARR="$(jq -s "[ .[] | $JQ_FILTER ]" "${files[@]}")"

if [ "$mode" = "text" ]; then
  if [ "$(echo "$JSON_ARR" | jq 'length')" = "0" ]; then
    echo "(no bugs match)"
  else
    echo "$JSON_ARR" | jq -r '.[] | "\(.name)  [\(.status)]  \(.title)"'
  fi
else
  echo "$JSON_ARR"
fi
exit 0
