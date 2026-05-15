#!/usr/bin/env python3
"""Drift oracle for workspace-generated artifacts."""
import filecmp
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CONTRACT = os.path.join(REPO_ROOT, ".claude/features/contract/build-contract.json")
BUILD_SH = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/build.py")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-generated-surface.py")

# t1
if os.path.isfile(BUILD_SH) and os.access(BUILD_SH, os.X_OK):
    ok(1, "build.py exists and is executable")
else:
    fail_t(1, f"build.py not found or not executable at {BUILD_SH}")

# t2
if os.path.isfile(CONTRACT):
    ok(2, "build-contract.json exists")
else:
    fail_t(2, f"build-contract.json not found at {CONTRACT}")

if fail_n > 0:
    print()
    print(f"Results: {pass_n} passed, {fail_n} failed")
    sys.exit(1)

# t3+
with open(CONTRACT) as f:
    contract = json.load(f)

t = 3
for target in contract["targets"]:
    if target.get("check_on_stop") and target["type"] == "copy-file":
        name = target["name"]
        src_abs = os.path.join(REPO_ROOT, target["source"])
        dst_abs = os.path.join(REPO_ROOT, target["destination"])
        if not os.path.isfile(dst_abs):
            fail_t(t, f"{name}: destination missing ({target['destination']})")
        elif filecmp.cmp(src_abs, dst_abs, shallow=False):
            ok(t, f"{name}: matches source")
        else:
            fail_t(t, f"{name}: drifted from source")
        t += 1

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
