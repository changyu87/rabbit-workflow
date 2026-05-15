#!/usr/bin/env python3
"""Tests rabbit-workspace command removal and rabbit-workspace-map skill wiring."""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
FEATURE_JSON = os.path.join(CAGE_DIR, "feature.json")

failures = 0


def ok(t, msg):
    print(f"  PASS t{t}: {msg}")


def fail_t(t, msg):
    global failures
    print(f"  FAIL t{t}: {msg}")
    failures += 1


print("test-rabbit-workspace-map-wiring.py")
print()

# t1
if not os.path.exists(os.path.join(CAGE_DIR, "commands/rabbit-workspace.md")):
    ok(1, "commands/rabbit-workspace.md does not exist (correctly removed)")
else:
    fail_t(1, "commands/rabbit-workspace.md still exists — must be removed (workspace hierarchy owned by rabbit-workspace-map)")

# t2
contract_feature_json = os.path.join(REPO_ROOT, ".claude/features/contract/feature.json")
try:
    with open(contract_feature_json) as f:
        d = json.load(f)
    skills_list = d.get("surface", {}).get("skills", [])
    if skills_list == []:
        ok(2, "contract/feature.json surface.skills is [] (skills retired from surface.skills mechanism)")
    else:
        fail_t(2, f"contract/feature.json surface.skills is not [] (expected retirement; current: {skills_list})")
except Exception:
    fail_t(2, "contract/feature.json could not be parsed")

# t3
try:
    with open(FEATURE_JSON) as f:
        d = json.load(f)
    cmds = d.get("surface", {}).get("commands", [])
    if not any("rabbit-workspace" in c for c in cmds):
        ok(3, "feature.json commands list does not contain rabbit-workspace")
    else:
        fail_t(3, f"feature.json commands list still contains a rabbit-workspace entry (current: {cmds})")
except Exception:
    fail_t(3, "feature.json could not be parsed")

# t4
contract_md = os.path.join(CAGE_DIR, "docs/spec/contract.md")
with open(contract_md) as f:
    cm = f.read()
if "workspace-tree.sh" in cm:
    fail_t(4, "contract.md still references workspace-tree.sh — must be removed from scripts list")
else:
    ok(4, "contract.md does not reference workspace-tree.sh (correctly removed from contract)")

# t5
if "rabbit-workspace-map" in cm:
    fail_t(5, "rabbit-cage contract.md still references rabbit-workspace-map — ownership moved to contract feature; remove from rabbit-cage contract.md")
else:
    ok(5, "rabbit-cage contract.md does not reference rabbit-workspace-map (correctly removed; owned by contract)")

print()
print(f"Results: {5 - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
