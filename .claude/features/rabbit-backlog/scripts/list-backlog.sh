#!/bin/bash
# list-backlog.sh -- list backlog items from centralized .claude/backlogs/ storage.
#
# Usage:
#   list-backlog.sh                                # all items, JSON array
#   list-backlog.sh --status open|in-progress|implemented|refused|reopened
#   list-backlog.sh --feature NAME[,NAME2]         # only named features
#   list-backlog.sh --text                         # human-readable: NAME  [STATUS]  [PRIORITY]  TITLE per line
#   list-backlog.sh -h|--help
#
# Algorithm:
#   1. Find REPO_ROOT (RABBIT_ROOT or git)
#   2. Find all subdirectories under $REPO_ROOT/.claude/backlogs/ (one level deep)
#   3. Each subdir is a feature bucket; collect all item.json files from each
#   4. Apply --feature filter by matching subdir name
#   5. Apply --status filter
#   6. Output JSON array or text
#
# Exit: 0 on success, 2 on usage error.

set -u

if [ -n "${RABBIT_ROOT:-}" ]; then
  REPO_ROOT="$RABBIT_ROOT"
else
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -z "$REPO_ROOT" ]; then
    echo "error: cannot determine repo root" 1>&2; exit 1
  fi
fi

mode="json"
filter_status=""
filter_features=()

while [ $# -gt 0 ]; do
  case "$1" in
    --status)
      filter_status="$2"; shift 2 ;;
    --feature)
      IFS=',' read -ra _parts <<< "$2"
      for _p in "${_parts[@]}"; do filter_features+=("$_p"); done
      shift 2 ;;
    --text) mode="text"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" 1>&2; exit 2 ;;
  esac
done

tmpfiles="$(mktemp)"
trap 'rm -f "$tmpfiles"' EXIT

feature_wanted() {
  local fname="$1"
  if [ "${#filter_features[@]}" -eq 0 ]; then return 0; fi
  for _f in "${filter_features[@]}"; do
    if [ "$_f" = "$fname" ]; then return 0; fi
  done
  return 1
}

BACKLOGS_ROOT="$REPO_ROOT/.claude/backlogs"

if [ -d "$BACKLOGS_ROOT" ]; then
  for bucket_dir in "$BACKLOGS_ROOT"/*/; do
    [ -d "$bucket_dir" ] || continue
    bucket_name="$(basename "$bucket_dir")"
    feature_wanted "$bucket_name" || continue
    for d in "$bucket_dir"*/; do
      [ -f "$d/item.json" ] && echo "$d/item.json" >> "$tmpfiles"
    done
  done
fi

mapfile -t files < "$tmpfiles"

if [ "${#files[@]}" -eq 0 ]; then
  if [ "$mode" = "text" ]; then echo "(no items)"; else echo "[]"; fi
  exit 0
fi

JQ_FILTER="."
if [ -n "$filter_status" ]; then
  JQ_FILTER="$JQ_FILTER | select(.status == \"$filter_status\")"
fi

JSON_ARR="$(jq -s "[ .[] | $JQ_FILTER ]" "${files[@]}")"

if [ "$mode" = "text" ]; then
  if [ "$(echo "$JSON_ARR" | jq 'length')" = "0" ]; then
    echo "(no items match)"
  else
    echo "$JSON_ARR" | jq -r '.[] | "\(.name)  [\(.status)]  [\(.priority)]  \(.title)"'
  fi
else
  echo "$JSON_ARR"
fi
exit 0
