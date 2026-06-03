#!/usr/bin/env python3
"""rabbit-config test runner — executes every suite in declaration order;
exits non-zero on any failure."""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SUITES = [
    "test-feature-json-shape.py",
    "test-skill-structure.py",
    "test-skill-description.py",
    "test-interpreter-unknown-subcommand.py",
    "test-interpreter-value-dispatch.py",
    "test-interpreter-action-dispatch.py",
    "test-interpreter-template-substitution.py",
    "test-interpreter-validation.py",
    "test-runtime-alerts-shape.py",
    "test-runtime-banner-shape.py",
    "test-verification-hygiene.py",
    "test-workspace-declares-rabbit-config.py",
    "test-restart-required-emits-prompt.py",
    "test-spec-layout.py",
]


def main() -> int:
    print("rabbit-config test runner")
    print()
    total_fail = 0
    for suite in SUITES:
        print(f"=== {suite} ===")
        path = os.path.join(SCRIPT_DIR, suite)
        result = subprocess.run([sys.executable, path])
        if result.returncode != 0:
            total_fail += 1
        print()

    if total_fail == 0:
        print("ALL SUITES PASSED")
        return 0
    print(f"FAILED: {total_fail} suite(s) had failures")
    return 1


if __name__ == "__main__":
    sys.exit(main())
