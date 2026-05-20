#!/usr/bin/env python3
"""test-backlog-27-retirements.py — CONTRACT-BACKLOG-27.

End-to-end regression that the following dead/orphan/retired artifacts have
been deleted from the contract feature surface:

  t1: scripts/dispatch-feature-edit.py is absent
  t2: scripts/workspace-map.py is absent
  t3: scripts/enforcement/check-no-main-edits.py is absent
  t4: scripts/enforcement/check-opus-for-planning-agents.py is absent
  t5: skills/rabbit-workspace-map/ source dir is absent
  t6: .claude/skills/rabbit-workspace-map/ deployed dir is absent
  t7: build-contract.json does not declare a rabbit-workspace-map skill entry
  t8: contract.lib.checks does not export check_no_main_edits or
      check_opus_for_planning_agents functions
  t9: contract/feature.json version >= 1.19.0

Exit 0 on pass, 1 on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when an automated dead-code detector spanning the
whole repo is wired into the Stop hook (subsumed by Inv 41 regression).
"""

import importlib.util
import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def ko(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    failed += 1


print("test-backlog-27-retirements.py")
print()


# t1-t4: deleted scripts absent
DELETED = [
    (1, "scripts/dispatch-feature-edit.py"),
    (2, "scripts/workspace-map.py"),
    (3, "scripts/enforcement/check-no-main-edits.py"),
    (4, "scripts/enforcement/check-opus-for-planning-agents.py"),
]
for n, rel in DELETED:
    p = os.path.join(FEATURE_DIR, rel)
    if os.path.exists(p):
        ko(n, f"{rel} still present at {p}")
    else:
        ok(n, f"{rel} is absent")


# t5: source skill dir absent
src_skill = os.path.join(FEATURE_DIR, "skills/rabbit-workspace-map")
if os.path.exists(src_skill):
    ko(5, f"source skill dir still present: {src_skill}")
else:
    ok(5, "skills/rabbit-workspace-map/ source dir is absent")


# t6: deployed skill dir absent
deployed_skill = os.path.join(REPO_ROOT, ".claude/skills/rabbit-workspace-map")
if os.path.exists(deployed_skill):
    ko(6, f"deployed skill dir still present: {deployed_skill}")
else:
    ok(6, ".claude/skills/rabbit-workspace-map/ deployed dir is absent")


# t7: build-contract.json does not declare rabbit-workspace-map skill
bc_path = os.path.join(FEATURE_DIR, "build-contract.json")
with open(bc_path) as f:
    bc = json.load(f)
ws_entries = [
    t for t in bc.get("targets", [])
    if "rabbit-workspace-map" in t.get("name", "")
    or "rabbit-workspace-map" in t.get("source", "")
    or "rabbit-workspace-map" in t.get("destination", "")
]
if ws_entries:
    ko(7, f"build-contract.json still declares rabbit-workspace-map entry: "
          f"{[e.get('name') for e in ws_entries]}")
else:
    ok(7, "build-contract.json declares no rabbit-workspace-map entry")


# t8: lib/checks.py does not export retired check functions
checks_path = os.path.join(FEATURE_DIR, "lib/checks.py")
spec = importlib.util.spec_from_file_location("contract_lib_checks_b27", checks_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
retired = ["check_no_main_edits", "check_opus_for_planning_agents"]
exported_retired = [name for name in retired if hasattr(mod, name)]
if exported_retired:
    ko(8, f"lib/checks.py still exports retired functions: {exported_retired}")
else:
    ok(8, "lib/checks.py does not export retired check functions")


# t9: contract/feature.json version bumped to >= 1.19.0
fj_path = os.path.join(FEATURE_DIR, "feature.json")
with open(fj_path) as f:
    fj = json.load(f)
version = fj.get("version", "0.0.0")


def vtuple(v):
    parts = v.split(".")
    return tuple(int(p) for p in parts[:3])


if vtuple(version) >= (1, 19, 0):
    ok(9, f"contract/feature.json version is {version} (>= 1.19.0)")
else:
    ko(9, f"contract/feature.json version is {version} (expected >= 1.19.0)")


print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
