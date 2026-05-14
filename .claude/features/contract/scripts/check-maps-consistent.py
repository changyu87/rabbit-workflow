#!/usr/bin/env python3
# check-maps-consistent.py — verify registry and filesystem are in sync.
#
# Usage (invoked by check-maps-consistent.sh):
#   python3 check-maps-consistent.py <features-dir> <registry-path>
#
# Verifies that every directory under <features-dir> containing a feature.json
# is listed in <registry-path>, and vice versa.
#
# Exit:
#   0 consistent
#   1 inconsistency found (descriptive error printed to stderr)
#   2 invocation error
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when registry.json is replaced by a native feature index.

import json
import os
import sys


def main():
    if len(sys.argv) != 3:
        print("usage: check-maps-consistent.py <features-dir> <registry-path>", file=sys.stderr)
        sys.exit(2)

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


if __name__ == '__main__':
    main()
