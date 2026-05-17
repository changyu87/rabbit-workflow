#!/usr/bin/env python3
# test-find-feature.py — tests for distributed feature registry lookup

import os
import sys
import subprocess
import json

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
# find-feature.py lives in the contract feature (cross-feature utility)
SCRIPT = os.path.join(REPO_ROOT, ".claude/features/contract/scripts/find-feature.py")
PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


# Test 1: script exists and is executable
if os.access(SCRIPT, os.X_OK):
    ok("script is executable")
else:
    fail("script not executable or missing")

# Test 2: find a known feature by name returns a path containing that name
r2 = subprocess.run(
    ["python3", SCRIPT, REPO_ROOT, "lookup", "contract"],
    capture_output=True, text=True
)
result = r2.stdout.strip()
if "features/contract" in result:
    ok("find contract returns correct path")
else:
    fail(f"find contract: got '{result}'")

# Test 3: unknown feature exits 1
r3 = subprocess.run(
    ["python3", SCRIPT, REPO_ROOT, "lookup", "no-such-feature"],
    capture_output=True
)
if r3.returncode == 1:
    ok("unknown feature exits 1")
else:
    fail(f"unknown feature exit code: {r3.returncode}")

# Test 4: list includes at least these core features (subset check — not exhaustive)
r4 = subprocess.run(
    ["python3", SCRIPT, REPO_ROOT, "list"],
    capture_output=True, text=True
)
lst = r4.stdout
for fname in ["contract", "policy", "rabbit-cage", "tdd-subagent"]:
    lines = [line.strip() for line in lst.split("\n")]
    if fname in lines:
        ok(f"list includes {fname}")
    else:
        fail(f"list missing {fname}")

# Test 5: list-json is a valid JSON array
r5 = subprocess.run(
    ["python3", SCRIPT, REPO_ROOT, "list-json"],
    capture_output=True, text=True
)
try:
    arr = json.loads(r5.stdout)
    if isinstance(arr, list):
        ok("list-json is valid JSON array")
    else:
        fail("list-json not a list")
except json.JSONDecodeError:
    fail("list-json not valid JSON")
    arr = []

# Test 6: list-json entries have required fields (name, path, summary, tdd_state)
try:
    for e in arr:
        for f in ("name", "path", "summary", "tdd_state"):
            if f not in e:
                raise AssertionError(f"missing field {f} in {e}")
    ok("list-json entries have all required fields")
except AssertionError as e:
    fail(f"list-json entries missing fields: {e}")

# Test 7: returned path exists on disk (handles both absolute and relative paths)
path = result  # from Test 2
if os.path.isdir(path) or os.path.isdir(os.path.join(REPO_ROOT, path)):
    ok("returned path exists on disk")
else:
    fail(f"path not on disk: '{path}'")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
