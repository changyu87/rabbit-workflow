#!/usr/bin/env python3
"""test-workspace-declares-rabbit-config.py — Inv 17.

  t17: workspace-structure.json declares rabbit-config as a required feature
       under features.children
"""

import json
import os
import subprocess
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
DECL = os.path.join(REPO_ROOT, ".claude/workspace-structure.json")

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


if not os.path.isfile(DECL):
    fail(17, f"workspace-structure.json not found at {DECL}")
    sys.exit(1)

with open(DECL) as f:
    decl = json.load(f)

features_node = next((n for n in decl.get("nodes", []) if n.get("name") == "features"), None)
if features_node is None:
    fail(17, "no 'features' node in workspace-structure.json")
    sys.exit(1)

children = {c["name"]: c for c in features_node.get("children", [])}

if "rabbit-config" not in children:
    fail(17, "rabbit-config not declared in workspace-structure.json features.children")
else:
    node = children["rabbit-config"]
    if not node.get("required"):
        fail(17, f"rabbit-config.required must be true, got {node.get('required')!r}")
    else:
        ok(17, "rabbit-config declared as required in workspace-structure.json")

if FAIL:
    print("test-workspace-declares-rabbit-config: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-workspace-declares-rabbit-config: all checks passed.")
