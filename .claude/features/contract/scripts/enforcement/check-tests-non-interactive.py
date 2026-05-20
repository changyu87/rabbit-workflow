#!/usr/bin/env python3
"""check-tests-non-interactive.py — thin CLI shim around
contract.lib.checks.check_tests_non_interactive (spec Inv 17, Inv 44).

Usage: check-tests-non-interactive.py <feature-dir>
Exit:  0 ok (no test/ dir, or test/ clean); 1 violations found; 2 invocation error.

Version: 3.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when non-interactive enforcement is provided by a native linter.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_tests_non_interactive  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check-tests-non-interactive.py <feature-dir>", file=sys.stderr)
        return 2
    result = check_tests_non_interactive(sys.argv[1])
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
