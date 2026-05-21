#!/usr/bin/env python3
"""Tests no .sh files in hooks/scripts and Inv 18 Python helpers exist."""
import glob
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
HOOKS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


print("test-no-embedded-python3.py")
print()

print("=== hooks/ has no .sh files ===")
sh_in_hooks = sorted(glob.glob(os.path.join(HOOKS_DIR, "*.sh")))
if not sh_in_hooks:
    ok("hooks/ has no .sh files")
else:
    fail_t(f"hooks/ still contains .sh files: {' '.join(sh_in_hooks)}")

print("=== scripts/ has no .sh files ===")
sh_in_scripts = sorted(glob.glob(os.path.join(SCRIPTS_DIR, "*.sh")))
if not sh_in_scripts:
    ok("scripts/ has no .sh files")
else:
    fail_t(f"scripts/ still contains .sh files: {' '.join(sh_in_scripts)}")

for pyfile in (
    "workspace-tree.py",
    "rabbit-project-set-path.py",
    "rabbit-project-map.py",
    "rabbit-project-consolidate.py",
    "build-targets.py",
    "generate-claude-md-header.py",
):
    print(f"=== {pyfile} exists ===")
    if os.path.isfile(os.path.join(SCRIPTS_DIR, pyfile)):
        ok(f"{pyfile} exists")
    else:
        fail_t(f"{pyfile} does not exist (expected Python helper per Inv 18)")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
