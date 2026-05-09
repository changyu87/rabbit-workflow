#!/bin/bash
# relink.sh — create/refresh symlinks declared in each feature's surface block.
#
# Usage:
#   relink.sh <features-dir>
#
# Reads registry.json from <features-dir>, iterates features, and logs what
# symlinks it would create. Idempotent.
#
# STUB: Full implementation in Step 4. Currently logs planned actions only.
#
# Exit:
#   0 success
#   1 features-dir or registry.json missing
#   2 invocation error

set -u

if [ $# -ne 1 ]; then
  echo "ERROR: usage: relink.sh <features-dir>" >&2
  exit 2
fi

FEATURES_DIR="$1"

if [ ! -d "$FEATURES_DIR" ]; then
  echo "ERROR: features-dir does not exist: $FEATURES_DIR" >&2
  exit 1
fi

REGISTRY="$FEATURES_DIR/registry.json"

if [ ! -f "$REGISTRY" ]; then
  echo "ERROR: registry.json not found: $REGISTRY" >&2
  exit 1
fi

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

with open(registry_path) as f:
    registry = json.load(f)

features = registry.get("features", {})

for name, entry in features.items():
    path = entry.get("path", "")
    print(f"[stub] feature '{name}' at '{path}'")
    fj_path = os.path.join(features_dir, name, "feature.json")
    if os.path.isfile(fj_path):
        with open(fj_path) as f:
            data = json.load(f)
        surface = data.get("surface", {})
        hooks = surface.get("hooks", [])
        commands = surface.get("commands", [])
        agents = surface.get("agents", [])
        skills = surface.get("skills", [])
        for item in hooks + commands + agents + skills:
            print(f"  [stub] would symlink: {item}")
    else:
        print(f"  [stub] feature.json not found at {fj_path}")

print("[stub] relink complete — no symlinks created (Step 4 will implement)")
PYEOF
