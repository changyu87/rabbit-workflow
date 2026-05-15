#!/usr/bin/env python3
# rabbit-bug test runner
# Executes all test suites in sequence; exits non-zero on any failure.

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

total_fail = 0


def run_suite(script):
    global total_fail
    print(f"=== {script} ===")
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, script)],
        check=False,
    )
    if result.returncode != 0:
        total_fail += 1
    print("")


print("rabbit-bug test runner")
print("")

run_suite("test-bug-scripts.py")
run_suite("test-bug-skill.py")
run_suite("test-bug-changes.py")
run_suite("test-bug-git-isolation.py")
run_suite("test-bug-workspace-map.py")
run_suite("test-bug-surface-skills.py")
run_suite("test-bug-main-branch.py")

if total_fail == 0:
    print("ALL SUITES PASSED")
    sys.exit(0)
else:
    print(f"FAILED: {total_fail} suite(s) had failures")
    sys.exit(1)
