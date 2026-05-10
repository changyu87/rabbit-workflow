#!/bin/bash
# list-bugs.sh — list bugs from all features in the full repo tree.
#
# Usage:
#   list-bugs.sh                          # all bugs from all features in repo tree, JSON
#   list-bugs.sh --status <s>             # filter by status (open|closed|reopened)
#   list-bugs.sh --feature <n>[,<n2>...]  # only bugs from named feature(s); can appear multiple times
#   list-bugs.sh --text                   # human-readable: "NAME  [STATUS]  TITLE" per line
#   list-bugs.sh -h|--help
#
# Algorithm:
#   1. Find REPO_ROOT (git rev-parse --show-toplevel or $RABBIT_ROOT)
#   2. Find all feature.json files under REPO_ROOT (excluding .git)
#   3. For each feature.json, read bugs_root field; skip if absent or dir missing
#   4. Collect all bug.json files from each bugs_root
#   5. Apply --feature filter (match feature "name" field in feature.json)
#   6. Apply --status filter
#   7. Output JSON array (default) or text (--text)
#
# Exit: 0 on success.

set -u

# ---------------------------------------------------------------------------
# Locate repo root
# ---------------------------------------------------------------------------
if [ -n "${RABBIT_ROOT:-}" ]; then
  REPO_ROOT="$RABBIT_ROOT"
else
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -z "$REPO_ROOT" ]; then
    echo "error: cannot determine repo root (not a git repo and RABBIT_ROOT not set)" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
mode="json"
filter_status=""
filter_features=()   # accumulates feature names

while [ $# -gt 0 ]; do
  case "$1" in
    --status)
      filter_status="$2"
      shift 2
      ;;
    --feature)
      # split comma-separated values
      IFS=',' read -ra _parts <<< "$2"
      for _p in "${_parts[@]}"; do
        filter_features+=("$_p")
      done
      shift 2
      ;;
    --text)
      mode="text"
      shift
      ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Collect bug.json files from all feature.json entries
# ---------------------------------------------------------------------------
# Files are accumulated in a temp file so we can pass them to jq later.
tmpfiles="$(mktemp)"
trap 'rm -f "$tmpfiles"' EXIT

# Helper: check if a feature name is in filter_features list
feature_wanted() {
  local fname="$1"
  if [ "${#filter_features[@]}" -eq 0 ]; then
    return 0   # no filter → all features wanted
  fi
  for _f in "${filter_features[@]}"; do
    if [ "$_f" = "$fname" ]; then
      return 0
    fi
  done
  return 1
}

while IFS= read -r fj; do
  # Extract feature name and bugs_root using python3 (jq may not be on PATH everywhere)
  read -r feat_name bugs_root_rel <<< "$(python3 - "$fj" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        d = json.load(f)
    name = d.get("name", "")
    br   = d.get("bugs_root", "")
    print(name, br)
except Exception:
    print("", "")
PYEOF
)"

  # Skip if bugs_root absent
  [ -z "$bugs_root_rel" ] && continue

  # Apply --feature filter on feature name
  feature_wanted "$feat_name" || continue

  # Resolve bugs_root relative to REPO_ROOT
  bugs_dir="$REPO_ROOT/$bugs_root_rel"
  [ -d "$bugs_dir" ] || continue

  # Collect bug.json files under this bugs_dir
  for d in "$bugs_dir"/*/; do
    [ -f "$d/bug.json" ] && echo "$d/bug.json" >> "$tmpfiles"
  done

done < <(find "$REPO_ROOT" -name "feature.json" -not -path "*/.git/*" 2>/dev/null)

# ---------------------------------------------------------------------------
# Build output
# ---------------------------------------------------------------------------
mapfile -t files < "$tmpfiles"

if [ "${#files[@]}" -eq 0 ]; then
  if [ "$mode" = "text" ]; then
    echo "(no bugs)"
  else
    echo "[]"
  fi
  exit 0
fi

# Build jq filter
JQ_FILTER="."
if [ -n "$filter_status" ]; then
  JQ_FILTER="$JQ_FILTER | select(.status == \"$filter_status\")"
fi

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
