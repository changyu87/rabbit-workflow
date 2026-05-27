#!/usr/bin/env python3
"""rabbit-cage test runner — executes every suite in declaration order;
exits non-zero on any failure."""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SUITES = [
    "test-structure.py",
    "test-version-alignment.py",
    "test-feature-json-validity.py",
    "test-icon-glyphs.py",
    "test-claude-md-imports-resolve.py",
    "test-claude-md-no-stale-imports.py",
    "test-dispatcher-lib.py",
    "test-dispatchers.py",
    "test-deployed-hooks-execute.py",
    "test-install-publish-loop.py",
    "test-scope-guard-centralized.py",
    "test-scope-guard-allowlist.py",
    "test-scope-guard-deny-message.py",
    "test-scope-guard-rabbit-allowlist.py",
    "test-scope-per-feature-marker.py",
    "test-RABBIT-CAGE-17-quoted-strings.py",
    "test-repo-permissions.py",
    "test-RABBIT-CAGE-BUG-104-hook-path-format.py",
]


def main() -> int:
    print("rabbit-cage test runner")
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
