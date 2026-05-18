#!/usr/bin/env python3
# rabbit-project-consolidate.py — check consistency of project-map.json vs features/registry.json
# Usage: python3 rabbit-project-consolidate.py <project_map_path> <registry_path> <project_name>
import json, sys, os

USAGE = "Usage: rabbit-project-consolidate.py <project_map_path> <registry_path> <project_name>\n"

if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
    sys.stdout.write(USAGE)
    sys.exit(0)
if len(sys.argv) < 4:
    sys.stderr.write(USAGE)
    sys.exit(2)

map_path = sys.argv[1]
reg_path = sys.argv[2]
name = sys.argv[3]

with open(map_path) as f:
    pmap = json.load(f)

source_map = pmap.get("source_map", {})
mapped_features = set(source_map.values())

registry_features = set()
if os.path.isfile(reg_path):
    with open(reg_path) as f:
        reg = json.load(f)
    registry_features = set(reg.get("features", {}).keys())

warnings = 0

for feat in sorted(registry_features):
    if feat not in mapped_features:
        print(f"note: feature {feat} has no source_map entry in project-map.json", file=sys.stderr)

for src, feat in sorted(source_map.items()):
    if feat not in registry_features:
        print(f"warning: source_map refers to unknown feature {feat}", file=sys.stderr)
        warnings += 1

paths = sorted(source_map.keys())
for i, a in enumerate(paths):
    for b in paths[i+1:]:
        if b.startswith(a) or a.startswith(b):
            print(f"warning: overlapping paths: {a} and {b}", file=sys.stderr)
            warnings += 1

# BUG-45: emit non-zero on any warning so callers can detect inconsistencies.
sys.exit(1 if warnings else 0)
