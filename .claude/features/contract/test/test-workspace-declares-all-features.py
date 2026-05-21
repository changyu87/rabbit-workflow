#!/usr/bin/env python3
"""test-workspace-declares-all-features.py — Inv 31.

`.claude/workspace-structure.json` MUST declare nodes for every feature that
exists on disk under `.claude/features/`. The runtime check via
`workspace-map.py --audit` was retired in CONTRACT-BACKLOG-27; this test
now validates the declaration shape directly.

  t1: Every directory under .claude/features/ has a corresponding entry in
      the features node of .claude/workspace-structure.json.
  t3: Specifically — Cycle B-added features rabbit-spec, rabbit-file, and
      rabbit-feature are declared in workspace-structure.json.
"""

import os
import sys
import json
import subprocess

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

DECL = os.path.join(REPO_ROOT, ".claude/workspace-structure.json")
FEATURES_DIR = os.path.join(REPO_ROOT, ".claude/features")

FAIL = 0


def fail_t(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


# Load declaration
with open(DECL) as f:
    decl = json.load(f)

features_node = next((n for n in decl["nodes"] if n["name"] == "features"), None)
if features_node is None:
    fail_t(0, "workspace-structure.json has no 'features' node")
    sys.exit(1)

declared_features = {c["name"] for c in features_node.get("children", [])}
on_disk_features = {
    name for name in os.listdir(FEATURES_DIR)
    if os.path.isdir(os.path.join(FEATURES_DIR, name))
}

# t1: every on-disk feature is declared
missing = on_disk_features - declared_features
if missing:
    fail_t(1, f"features on disk but not declared: {sorted(missing)}")
else:
    ok(1, f"all {len(on_disk_features)} on-disk features declared in workspace-structure.json")

# t3: Cycle B features are present in declaration
required = {"rabbit-spec", "rabbit-file", "rabbit-feature"}
missing_cycle_b = required - declared_features
if missing_cycle_b:
    fail_t(3, f"Cycle B features missing from declaration: {sorted(missing_cycle_b)}")
else:
    ok(3, "rabbit-spec, rabbit-file, rabbit-feature declared in workspace-structure.json")

if FAIL:
    print("test-workspace-declares-all-features: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-workspace-declares-all-features: all checks passed.")
