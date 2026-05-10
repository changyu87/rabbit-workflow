#!/bin/bash
# check-maps-consistent.sh — verify registry and filesystem are in sync.
#
# Usage:
#   check-maps-consistent.sh <features-dir>
#
# Verifies that every directory under <features-dir> containing a feature.json
# is listed in <features-dir>/registry.json, and vice versa.
#
# Exit:
#   0 consistent
#   1 inconsistency found (descriptive error printed to stderr)
#   2 invocation error

set -u

if [ $# -ne 1 ]; then
  echo "ERROR: usage: check-maps-consistent.sh <features-dir>" >&2
  exit 2
fi

FEATURES_DIR="$1"

if [ ! -d "$FEATURES_DIR" ]; then
  echo "ERROR: features-dir does not exist: $FEATURES_DIR" >&2
  exit 2
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

# Collect all directories with feature.json.
fs_features = set()
for dirpath, dirnames, filenames in os.walk(features_dir):
    if "feature.json" in filenames:
        fj_path = os.path.join(dirpath, "feature.json")
        try:
            with open(fj_path) as f:
                data = json.load(f)
            name = data.get("name")
            if name:
                fs_features.add(name)
        except Exception as e:
            print(f"WARNING: could not parse {fj_path}: {e}", file=sys.stderr)

# Load registry features.
with open(registry_path) as f:
    registry = json.load(f)
reg_features = set(registry.get("features", {}).keys())

in_fs_not_reg = fs_features - reg_features
in_reg_not_fs = reg_features - fs_features

errors = []
if in_fs_not_reg:
    errors.append(f"Features on disk but not in registry: {sorted(in_fs_not_reg)}")
if in_reg_not_fs:
    errors.append(f"Features in registry but not on disk: {sorted(in_reg_not_fs)}")

if errors:
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

print(f"OK: {len(fs_features)} features consistent between disk and registry.")
sys.exit(0)
PYEOF
