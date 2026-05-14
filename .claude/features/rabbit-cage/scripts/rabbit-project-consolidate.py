#!/usr/bin/env python3
# rabbit-project-consolidate.py — check consistency of project-map.json vs features/registry.json
# Usage: python3 rabbit-project-consolidate.py <project_map_path> <registry_path> <project_name>
import json, sys, os

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

for feat in sorted(registry_features):
    if feat not in mapped_features:
        print(f"note: feature {feat} has no source_map entry in project-map.json", file=sys.stderr)

for src, feat in sorted(source_map.items()):
    if feat not in registry_features:
        print(f"warning: source_map refers to unknown feature {feat}", file=sys.stderr)

paths = sorted(source_map.keys())
for i, a in enumerate(paths):
    for b in paths[i+1:]:
        if b.startswith(a) or a.startswith(b):
            print(f"warning: overlapping paths: {a} and {b}", file=sys.stderr)
