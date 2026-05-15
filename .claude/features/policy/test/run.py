#!/usr/bin/env python3
# run.py — Master test runner for the policy feature.
# Executes all test scripts in sequence. Exits non-zero on any failure.
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_test(script):
    print(f"==> Running: {script}")
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, script)],
    )
    if result.returncode != 0:
        sys.exit(result.returncode)
    print(f"    PASS: {script}")


run_test("test-files-exist.py")
run_test("test-rule-files-content.py")
run_test("test-imports-resolve.py")
run_test("test-backlog003.py")
run_test("test-policy-invariants-v1-2-0.py")
run_test("test-POLICY-1-no-stale-imports.py")

print()
print("All tests passed.")
