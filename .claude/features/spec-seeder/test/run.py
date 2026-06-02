#!/usr/bin/env python3
"""spec-seeder test runner — discovers and runs every test-*.py in this dir.

Exits 0 iff every test-*.py exits 0. Aggregates per-file results to stdout.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: superseded when a repo-wide test runner replaces per-feature runners
"""

import glob
import os
import subprocess
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    test_files = sorted(glob.glob(os.path.join(TEST_DIR, "test-*.py")))
    if not test_files:
        sys.stderr.write("no test-*.py files found in spec-seeder/test/\n")
        return 1

    failed = []
    for tf in test_files:
        name = os.path.basename(tf)
        print(f"=== {name} ===")
        result = subprocess.run(["python3", tf], capture_output=False)
        if result.returncode == 0:
            print(f"--- PASS: {name} ---")
        else:
            print(f"--- FAIL: {name} (exit {result.returncode}) ---")
            failed.append(name)

    print()
    if failed:
        print(f"FAILED: {len(failed)} / {len(test_files)}: {failed}")
        return 1
    print(f"ALL TESTS PASSED ({len(test_files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
