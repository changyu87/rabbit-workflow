#!/bin/bash
# file-bug.sh -- file a new bug under centralized .claude/bugs/ storage.
# Usage: file-bug.sh --title T --severity S --description D [--related-feature F] [--filed-by A]
# Exit: 0=ok 1=val-err 2=inv-err

set -u

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
REGISTRY="$REPO_ROOT/.claude/features/registry.json"
BUG_PREFIX="${BUG_PREFIX:-RBT}"

usage() {
  echo "usage: file-bug.sh --title T --severity {low|medium|high|critical} --description D [--related-feature F] [--filed-by A]" 1>&2
}

TITLE=""; SEV=""; DESC=""; FEAT=""; FILER=""

while [ $# -gt 0 ]; do
  case "$1" in
    --title)           TITLE="$2"; shift 2 ;;
    --severity)        SEV="$2"; shift 2 ;;
    --description)     DESC="$2"; shift 2 ;;
    --related-feature) FEAT="$2"; shift 2 ;;
    --filed-by)        FILER="$2"; shift 2 ;;
    -h|--help)         usage; exit 0 ;;
    *)                 echo "unknown arg: $1" 1>&2; usage; exit 2 ;;
  esac
done

[ -z "$TITLE" ] && { echo "ERROR: --title required" 1>&2; exit 1; }
[ -z "$SEV" ]   && { echo "ERROR: --severity required" 1>&2; exit 1; }
[ -z "$DESC" ]  && { echo "ERROR: --description required" 1>&2; exit 1; }

case "$SEV" in
  low|medium|high|critical) ;;
  *) echo "ERROR: invalid severity (allowed: low|medium|high|critical)" 1>&2; exit 1 ;;
esac

if [ -n "$FEAT" ]; then
  if ! echo "$FEAT" | grep -qE '^[a-z][a-z0-9-]{0,49}$'; then
    echo "ERROR: --related-feature must match [a-z][a-z0-9-]* (max 50 chars)" 1>&2; exit 1
  fi
fi

# Determine BUG_ROOT and PREFIX based on --related-feature
if [ -n "$FEAT" ]; then
  # Validate feature exists in registry.json
  FEAT_EXISTS="$(python3 - "$REGISTRY" "$FEAT" <<'PYEOF'
import json, sys
registry_path, feat_name = sys.argv[1], sys.argv[2]
try:
    with open(registry_path) as f:
        d = json.load(f)
    features = d.get("features", {})
    if feat_name in features:
        print("found")
    else:
        print("not_found")
except Exception:
    print("not_found")
PYEOF
)"
  if [ "$FEAT_EXISTS" != "found" ]; then
    echo "ERROR: feature '$FEAT' not found in registry.json" 1>&2; exit 1
  fi
  FEATURE_NAME="$FEAT"
  PREFIX="$(echo "$FEAT" | tr '[:lower:]' '[:upper:]')"
  # Resolve canonical bugs root via workspace-map.sh (rabbit-workspace-map contract interface)
  BUGS_BASE="$(workspace-map.sh "$FEATURE_NAME" 2>/dev/null || echo "$REPO_ROOT/.claude/bugs")"
  BUG_ROOT="$BUGS_BASE/$FEATURE_NAME"
else
  # Resolve canonical bugs root via workspace-map.sh (rabbit-workspace-map contract interface)
  BUGS_BASE="$(workspace-map.sh 2>/dev/null || echo "$REPO_ROOT/.claude/bugs")"
  BUG_ROOT="$BUGS_BASE/unassigned"
  PREFIX="$BUG_PREFIX"
fi

MAX=0
if [ -d "$BUG_ROOT" ]; then
  # Scan bug.json name fields
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    existing_name="$(jq -r '.name // ""' "$f" 2>/dev/null)"
    if echo "$existing_name" | grep -qE "^${PREFIX}-([1-9][0-9]*)$"; then
      n="$(echo "$existing_name" | sed -E "s/^${PREFIX}-//")"
      [ "$n" -gt "$MAX" ] 2>/dev/null && MAX="$n"
    fi
  done < <(find "$BUG_ROOT" -name "bug.json" -maxdepth 2)
  # Also scan directory names to avoid collisions with misnamed bugs
  while IFS= read -r d; do
    dname="$(basename "$d")"
    if echo "$dname" | grep -qE "^${PREFIX}-([1-9][0-9]*)$"; then
      n="$(echo "$dname" | sed -E "s/^${PREFIX}-//")"
      [ "$n" -gt "$MAX" ] 2>/dev/null && MAX="$n"
    fi
  done < <(find "$BUG_ROOT" -mindepth 1 -maxdepth 1 -type d)
fi
N=$((MAX + 1))
NAME="${PREFIX}-${N}"

BUG_DIR="$BUG_ROOT/$NAME"
[ -e "$BUG_DIR" ] && { echo "ERROR: bug already exists at $BUG_DIR" 1>&2; exit 1; }
[ -z "$FILER" ] && FILER="${USER:-unknown}"

mkdir -p "$BUG_DIR"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

jq -n --arg name "$NAME" --arg title "$TITLE" --arg sev "$SEV" \
  --arg desc "$DESC" --arg feat "$FEAT" --arg filer "${FILER:-${USER:-unknown}}" --arg ts "$TS" \
  '{name:$name,title:$title,status:"open",severity:$sev,description:$desc,
    related_feature:(if $feat=="" then null else $feat end),
    filed:$ts,filed_by:$filer,closed:null,closed_by:null,
    history:[{ts:$ts,actor:$filer,action:"opened",note:"initial filing"}]}' \
  > "$BUG_DIR/bug.json"

REPO_ROOT="$(git -C "$BUG_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$REPO_ROOT" ]; then
  git -C "$REPO_ROOT" add "$BUG_DIR/bug.json" 2>/dev/null && \
  git -C "$REPO_ROOT" commit -m "bug: file $NAME ($TITLE)" 2>/dev/null || true
fi

echo "filed: $BUG_DIR/bug.json  [$NAME]"
exit 0
