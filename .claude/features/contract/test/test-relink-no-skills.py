#!/usr/bin/env python3
# test-relink-no-skills.py
# t1: relink.sh does not create a repo-root symlink from skills surface entries
# t2: relink.sh header comment does not mention 'skills'

import os
import sys
import subprocess
import re

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RELINK = os.path.join(FEATURE_DIR, "scripts/relink.sh")

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def fail_t(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}")
    failed += 1


print("test-relink-no-skills.py")

T1_LABEL = "t1: relink.sh does not create rabbit-feature-touch symlink at repo root"
if not os.path.isfile(RELINK):
    # relink.sh was deleted — it cannot create any symlinks; vacuously true.
    ok(1, f"{T1_LABEL} (vacuously satisfied — relink.sh was deleted)")
else:
    # Run relink.sh and verify no skill-named symlink appears at repo root.
    subprocess.run(
        ["bash", RELINK, os.path.join(REPO_ROOT, ".claude/features"), REPO_ROOT],
        capture_output=True
    )
    touch_path = os.path.join(REPO_ROOT, "rabbit-feature-touch")
    if not os.path.exists(touch_path) and not os.path.islink(touch_path):
        ok(1, T1_LABEL)
    else:
        fail_t(1, f"{T1_LABEL} — found unexpected {touch_path}")

T2_LABEL = "t2: relink.sh header comment does not mention 'skills'"
if not os.path.isfile(RELINK):
    # relink.sh does not exist — vacuously true.
    ok(2, f"{T2_LABEL} (vacuously satisfied — relink.sh does not exist)")
else:
    content = open(RELINK).read()
    if not re.search(r'surface\.(hooks|commands|agents|skills)', content):
        ok(2, T2_LABEL)
    else:
        fail_t(2, f"{T2_LABEL} — header still documents 'skills'")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
