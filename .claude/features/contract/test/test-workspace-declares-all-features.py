#!/usr/bin/env python3
"""test-workspace-declares-all-features.py — Inv 38.

`.claude/workspace-structure.json` MUST declare nodes for every feature that
exists on disk under `.claude/features/`. Missing declarations cause
`workspace-map.py --audit` to emit a `warn`-severity finding (Inv 38).

This is an end-to-end test:
  t1: Every directory under .claude/features/ has a corresponding entry in
      the features node of .claude/workspace-structure.json.
  t2: Running `workspace-map.py --audit` does NOT emit any
      `type=unknown` finding whose path is a top-level feature directory
      (i.e., .claude/features/<feature-name>).
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
MAP_SCRIPT = os.path.join(REPO_ROOT, ".claude/features/contract/scripts/workspace-map.py")

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

# t2: workspace-map.py --audit emits no `unknown` finding for top-level feature dirs
r = subprocess.run(["python3", MAP_SCRIPT, "--audit"], capture_output=True, text=True)
audit = json.loads(r.stdout)
unknown_feature_findings = [
    f for f in audit.get("findings", [])
    if f.get("type") == "unknown"
    and f.get("path", "").startswith(".claude/features/")
    # only top-level feature dirs (one path segment under .claude/features/)
    and f["path"].count("/") == 3
]
if unknown_feature_findings:
    fail_t(2, f"audit emits unknown findings for top-level feature dirs: {[f['path'] for f in unknown_feature_findings]}")
else:
    ok(2, "audit emits no 'unknown' findings for top-level feature dirs")

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
