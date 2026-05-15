#!/usr/bin/env python3
# run.py — test runner for rabbit-backlog feature.
# Runs all test suites and aggregates results.

import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent

passed = 0
failed = 0
errors = []


def run_suite(script):
    global passed, failed
    name = script.name
    print(f"--- {name} ---")
    result = subprocess.run(
        [sys.executable, str(script)],
        text=True
    )
    if result.returncode == 0:
        print(f"  suite PASSED: {name}")
    else:
        print(f"  suite FAILED: {name}")
        errors.append(name)
        failed += 1
    print()


print("=== rabbit-backlog test runner ===")
print()

run_suite(TEST_DIR / "test-backlog-scripts.py")
run_suite(TEST_DIR / "test-backlog-skill.py")
run_suite(TEST_DIR / "test-backlog-state-machine.py")
run_suite(TEST_DIR / "test-workspace-map-invocation.py")
run_suite(TEST_DIR / "test-list-backlog.py")
run_suite(TEST_DIR / "test-surface-skills-empty.py")
run_suite(TEST_DIR / "test-branch-guard.py")

print("=== Summary ===")
if errors:
    print("Failed suites:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print("All suites passed.")
sys.exit(0)
