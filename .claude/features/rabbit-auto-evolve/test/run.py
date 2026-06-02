#!/usr/bin/env python3
"""run.py — run all rabbit-auto-evolve feature tests in sequence.

Non-interactive. Exits non-zero on first failure. Per contract Inv 17, this
runner MUST invoke every active test-*.py file in this directory.
"""

import os
import sys
import subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def run_test(script):
    print(f"=== {script} ===")
    result = subprocess.run(
        [sys.executable, os.path.join(TEST_DIR, script)]
    )
    if result.returncode != 0:
        print(f"--- FAIL: {script} ---", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"--- PASS: {script} ---")
    print()


run_test("test-set-evolve-mode.py")
run_test("test-fetch-queue.py")

print("ALL TESTS PASSED")
