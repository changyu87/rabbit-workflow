#!/bin/bash
# find-feature.sh — distributed feature registry lookup.
# Replaces registry.json as the authoritative feature index.
#
# Usage:
#   find-feature.sh <feature-name>   # print relative path to feature dir; exit 1 if not found
#   find-feature.sh --list            # print all feature names, one per line
#   find-feature.sh --list-json       # print [{name,path,summary,tdd_state},...] as JSON
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when feature discovery is handled natively by the dispatch infrastructure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${RABBIT_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$REPO_ROOT" ] && { echo "ERROR: cannot determine repo root" >&2; exit 1; }

CMD="${1:-}"

case "$CMD" in
  --list)
    python3 - "$REPO_ROOT" <<'PYEOF'
import json, os, sys, glob
repo = sys.argv[1]
paths = sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json')))
for entry in sorted(os.listdir(repo)):
    feat_base = os.path.join(repo, entry, 'features')
    if os.path.isdir(feat_base):
        for fname in sorted(os.listdir(feat_base)):
            fj = os.path.join(feat_base, fname, 'feature.json')
            if os.path.isfile(fj):
                paths.append(fj)
for fj in paths:
    try:
        name = json.load(open(fj)).get('name', '')
        if name:
            print(name)
    except Exception:
        pass
PYEOF
    exit 0
    ;;

  --list-json)
    python3 - "$REPO_ROOT" <<'PYEOF'
import json, os, sys, glob
repo = sys.argv[1]
results = []
# Rabbit-level features
for fj in sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json'))):
    try:
        f = json.load(open(fj))
        results.append({
            'name': f.get('name', ''),
            'path': os.path.relpath(os.path.dirname(fj), repo),
            'summary': f.get('summary', ''),
            'tdd_state': f.get('tdd_state', '')
        })
    except Exception:
        pass
# Project-level features
for entry in sorted(os.listdir(repo)):
    feat_base = os.path.join(repo, entry, 'features')
    if not os.path.isdir(feat_base):
        continue
    for fname in sorted(os.listdir(feat_base)):
        fj = os.path.join(feat_base, fname, 'feature.json')
        if os.path.isfile(fj):
            try:
                f = json.load(open(fj))
                results.append({
                    'name': f.get('name', ''),
                    'path': os.path.relpath(os.path.dirname(fj), repo),
                    'summary': f.get('summary', ''),
                    'tdd_state': f.get('tdd_state', '')
                })
            except Exception:
                pass
print(json.dumps(results))
PYEOF
    exit 0
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
    result=$(python3 - "$REPO_ROOT" "$FEATURE_NAME" <<'PYEOF'
import json, os, sys, glob
repo = sys.argv[1]
target = sys.argv[2]
# Search rabbit-level features
for fj in sorted(glob.glob(os.path.join(repo, '.claude', 'features', '*', 'feature.json'))):
    try:
        f = json.load(open(fj))
        if f.get('name', '') == target:
            print(os.path.relpath(os.path.dirname(fj), repo))
            sys.exit(0)
    except Exception:
        pass
# Search project-level features
for entry in sorted(os.listdir(repo)):
    feat_base = os.path.join(repo, entry, 'features')
    if not os.path.isdir(feat_base):
        continue
    for fname in sorted(os.listdir(feat_base)):
        fj = os.path.join(feat_base, fname, 'feature.json')
        if os.path.isfile(fj):
            try:
                f = json.load(open(fj))
                if f.get('name', '') == target:
                    print(os.path.relpath(os.path.dirname(fj), repo))
                    sys.exit(0)
            except Exception:
                pass
PYEOF
)
    if [ -z "$result" ]; then
      echo "ERROR: feature '$FEATURE_NAME' not found" >&2
      exit 1
    fi
    echo "$result"
    ;;
esac
