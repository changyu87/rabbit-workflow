#!/usr/bin/env python3
"""End-to-end test runner for rabbit-feature.

Runs every test-*.py under this directory and exits non-zero on the first
failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent


def main() -> int:
    tests = sorted(TEST_DIR.glob("test-*.py"))
    if not tests:
        sys.stderr.write("no tests found in test/\n")
        return 1
    failed = 0
    for test in tests:
        print(f"=== {test.name} ===")
        result = subprocess.run(["python3", str(test)])
        if result.returncode != 0:
            failed += 1
            print(f"FAIL {test.name} (exit {result.returncode})", file=sys.stderr)
    if failed:
        print(f"{failed} test file(s) failed", file=sys.stderr)
        return 1
    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
