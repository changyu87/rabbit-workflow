#!/usr/bin/env python3
"""run.py — Master test runner for the policy feature.

Executes all test scripts in sequence. Exits non-zero on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when a higher-level harness invokes per-feature test
suites uniformly across the workflow.
"""
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


run_test("test-rule-files-content.py")
run_test("test-policy-invariants.py")
run_test("test-policy-bug-fixes.py")
run_test("test-historical-fixes-retirement.py")

print()
print("All tests passed.")
