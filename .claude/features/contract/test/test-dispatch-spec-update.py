#!/usr/bin/env python3
# Tests for dispatch-spec-update.py

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

result = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
SCRIPT = os.path.join(REPO_ROOT, ".claude/features/contract/scripts/dispatch-spec-update.py") if REPO_ROOT else ""

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  PASS {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


print("test-dispatch-spec-update.py")

# t1: script exists and is executable
if SCRIPT and os.path.isfile(SCRIPT) and os.access(SCRIPT, os.X_OK):
    ok("t1: dispatch-spec-update.py exists and is executable")
else:
    ko(f"t1: dispatch-spec-update.py missing or not executable at {SCRIPT}")

# t2: no args → exit 2
r2 = subprocess.run(["python3", SCRIPT], capture_output=True)
if r2.returncode == 2:
    ok("t2: no args exits 2")
else:
    ko(f"t2: expected exit 2 on no args, got {r2.returncode}")

# t3: unknown feature → exit 1
r3 = subprocess.run(
    ["python3", SCRIPT, "nonexistent-feature-xyz", "some change"],
    capture_output=True
)
if r3.returncode == 1:
    ok("t3: unknown feature exits 1")
else:
    ko(f"t3: expected exit 1 for unknown feature, got {r3.returncode}")

# t4: output starts with RABBIT-POLICY-BLOCK-v1 sentinel for known feature
r4 = subprocess.run(
    ["python3", SCRIPT, "rabbit-cage", "test change description"],
    capture_output=True, text=True
)
t4_out = r4.stdout
first_line = t4_out.split("\n")[0] if t4_out else ""
if "RABBIT-POLICY-BLOCK-v1" in first_line:
    ok("t4: output starts with RABBIT-POLICY-BLOCK-v1 sentinel")
else:
    ko(f"t4: sentinel missing; first line: '{first_line}'")

# t5: output contains spec content (spot-check: feature name present in spec)
if "rabbit-cage" in t4_out:
    ok("t5: output contains spec content (feature name present)")
else:
    ko("t5: spec content not injected into prompt")

# t6: output contains the change description
if "test change description" in t4_out:
    ok("t6: output contains the change description")
else:
    ko("t6: change description not in prompt output")

# t7: output contains SCOPE declaration for the feature
if "SCOPE: rabbit-cage" in t4_out:
    ok("t7: output contains SCOPE: rabbit-cage")
else:
    ko("t7: SCOPE declaration missing")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
