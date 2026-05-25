#!/usr/bin/env python3
"""Inv 1, 2, 28 — owned surface, no state-machine scripts in this feature,
feature.json surface arrays empty, feature.json conforms to flat schema."""
import json
import os
import sys

from _helpers import FEATURE_DIR, REPO_ROOT, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


# Inv 1: owned surface entries present (three entries post-v4.0.0 absorption).
dispatch = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
tdd_step = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")
agent = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
if os.path.isfile(dispatch):
    ok("inv1: scripts/dispatch-tdd-subagent.py exists")
else:
    ko("inv1: scripts/dispatch-tdd-subagent.py missing")
if os.path.isfile(tdd_step):
    ok("inv1: scripts/tdd-step.py exists (absorbed from tdd-state-machine)")
else:
    ko("inv1: scripts/tdd-step.py missing")
if os.path.isfile(agent):
    ok("inv1: agents/tdd-subagent.md exists")
else:
    ko("inv1: agents/tdd-subagent.md missing")

# Inv 1: only tdd-step.py belongs to the absorbed state-machine surface;
# the other historical state-machine scripts (tdd-context.py, tdd-drift-check.py)
# were retired and MUST NOT reappear under tdd-subagent/scripts/.
banned = {"tdd-context.py", "tdd-drift-check.py"}
scripts_dir = os.path.join(FEATURE_DIR, "scripts")
present = set(os.listdir(scripts_dir)) & banned
if present:
    ko(f"inv1: retired state-machine scripts present in scripts/: {sorted(present)}")
else:
    ok("inv1: no retired state-machine scripts in scripts/")

# Inv 2 + Inv 28: feature.json surface arrays empty, fields conform to flat schema.
feature_json = os.path.join(FEATURE_DIR, "feature.json")
with open(feature_json) as f:
    data = json.load(f)

required_flat_fields = {"name", "version", "owner", "tdd_state", "summary", "surface", "deprecation_criterion"}
missing = required_flat_fields - set(data.keys())
if missing:
    ko(f"inv28: feature.json missing flat fields: {sorted(missing)}")
else:
    ok("inv28: feature.json has all required flat fields")

surface = data.get("surface", {})
for key in ("hooks", "commands", "skills"):
    if surface.get(key) == []:
        ok(f"inv2: feature.json surface.{key} is []")
    else:
        ko(f"inv2: feature.json surface.{key} is not []: {surface.get(key)!r}")

# Inv 28: schema file exists under contract feature.
schema_path = os.path.join(
    REPO_ROOT, ".claude", "features", "contract", "schemas", "feature.json.schema.json"
)
if os.path.isfile(schema_path):
    ok("inv28: feature.json schema file exists under contract feature")
else:
    ko(f"inv28: schema file missing at {schema_path}")

report(passed, failed)
