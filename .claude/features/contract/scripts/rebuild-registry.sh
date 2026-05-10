#!/bin/bash
# rebuild-registry.sh — rebuild registry.json from feature.json files.
#
# Usage:
#   rebuild-registry.sh <features-dir>
#
# Reads all feature.json files under <features-dir> and writes
# <features-dir>/registry.json.
#
# Exit:
#   0 success
#   1 features-dir does not exist or is not a directory
#   2 invocation error

set -u

if [ $# -ne 1 ]; then
  echo "ERROR: usage: rebuild-registry.sh <features-dir>" >&2
  exit 2
fi

FEATURES_DIR="$1"

if [ ! -d "$FEATURES_DIR" ]; then
  echo "ERROR: features-dir does not exist or is not a directory: $FEATURES_DIR" >&2
  exit 1
fi

REGISTRY="$FEATURES_DIR/registry.json"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required" >&2
  exit 1
fi

python3 - "$FEATURES_DIR" "$REGISTRY" <<'PYEOF'
import json
import os
import sys

features_dir = sys.argv[1]
registry_path = sys.argv[2]

features = {}

for dirpath, dirnames, filenames in os.walk(features_dir):
    if "feature.json" in filenames:
        fj_path = os.path.join(dirpath, "feature.json")
        try:
            with open(fj_path) as f:
                data = json.load(f)
        except Exception as e:
            print(f"WARNING: could not parse {fj_path}: {e}", file=sys.stderr)
            continue

        name = data.get("name")
        if not name:
            print(f"WARNING: feature.json missing 'name': {fj_path}", file=sys.stderr)
            continue

        # Compute repo-relative path.
        rel_path = os.path.relpath(dirpath, start=os.path.dirname(os.path.dirname(features_dir)))

        entry = {
            "name": name,
            "version": data.get("version", ""),
            "owner": data.get("owner", ""),
            "tdd_state": data.get("tdd_state", ""),
            "summary": data.get("summary", ""),
            "path": rel_path,
        }
        features[name] = entry

registry = {
    "schema_version": "1.0.0",
    "owner": "rabbit-workflow team",
    "features": features,
}

with open(registry_path, "w") as f:
    json.dump(registry, f, indent=2)
    f.write("\n")

print(f"Written: {registry_path} ({len(features)} features)")
PYEOF
