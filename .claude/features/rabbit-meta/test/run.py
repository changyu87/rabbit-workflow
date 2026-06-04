#!/usr/bin/env python3
"""run.py — run all rabbit-meta feature tests in sequence.

Non-interactive. Exits non-zero on first failure. Per Inv 17, this runner
MUST invoke every active test-*.py file in this directory.
"""

import os
import sys
import subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def run_test(script):
    print(f"=== {script} ===")
    result = subprocess.run(
        ["python3", os.path.join(TEST_DIR, script)]
    )
    if result.returncode != 0:
        print(f"--- FAIL: {script} ---", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"--- PASS: {script} ---")
    print()


run_test("test-mode-detection.py")
run_test("test-generate-claude-md.py")
run_test("test-generate-readme.py")
run_test("test-owner-team.py")
run_test("test-specs-layout.py")
run_test("test-bb-vocab-retired.py")
run_test("test-spec-seeder-ownership-retired.py")
run_test("test-contiguous-invariants-optin.py")

print("ALL TESTS PASSED")
