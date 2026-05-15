#!/usr/bin/env python3
"""rabbit-cage split-validation tests."""
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


print("test-split-validation.py")

# t1-t5: scripts that should not exist
script_checks = [
    (1, "file-bug.sh", "rabbit-bug"),
    (2, "bug-status.sh", "rabbit-bug"),
    (3, "list-bugs.sh", "rabbit-bug"),
    (4, "file-backlog-item.sh", "rabbit-backlog"),
    (5, "backlog-item-status.sh", "rabbit-backlog"),
]

for t, fname, target in script_checks:
    p = os.path.join(CAGE_DIR, "scripts", fname)
    if not os.path.isfile(p):
        ok(t, f"{fname} does not exist in rabbit-cage/scripts/")
    else:
        fail_t(t, f"{fname} still exists in rabbit-cage/scripts/ — should be in {target}")

# t6: feature.json no bugs_root
try:
    with open(os.path.join(CAGE_DIR, "feature.json")) as f:
        d = json.load(f)
    if "bugs_root" not in d:
        ok(6, "feature.json does not have a bugs_root key")
    else:
        fail_t(6, "feature.json still has a bugs_root key — must be removed after split")
except Exception:
    fail_t(6, "feature.json could not be loaded")

# t7
if not os.path.isdir(os.path.join(CAGE_DIR, "docs/bugs")):
    ok(7, "docs/bugs/ directory does not exist in rabbit-cage")
else:
    fail_t(7, "docs/bugs/ still exists in rabbit-cage — should be moved to rabbit-bug")

# t8
if not os.path.isdir(os.path.join(CAGE_DIR, "docs/backlog")):
    ok(8, "docs/backlog/ directory does not exist in rabbit-cage")
else:
    fail_t(8, "docs/backlog/ still exists in rabbit-cage — should be moved to rabbit-backlog")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
