#!/usr/bin/env python3
"""check-imports-resolve.py — thin CLI shim around
contract.lib.checks.check_imports_resolve (spec Inv 32, Inv 44).

Usage: check-imports-resolve.py <feature-dir>
Exit:  0 all paths resolve (or no docs/); 1 missing paths; 2 invocation error.

Version: 2.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when import resolution is enforced by a native linter.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_imports_resolve  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check-imports-resolve.py <feature-dir>", file=sys.stderr)
        return 2
    result = check_imports_resolve(sys.argv[1])
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
