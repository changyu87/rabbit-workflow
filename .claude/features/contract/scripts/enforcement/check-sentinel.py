#!/usr/bin/env python3
"""check-sentinel.py — thin CLI shim around contract.lib.checks.check_sentinel
(spec Inv 20, Inv 37).

Usage: check-sentinel.py <file-or-dir>
Exit:  0 sentinel present; 1 missing; 2 invocation error.

Version: 2.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when sentinel enforcement is provided by a native linter.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_sentinel  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("ERROR: usage: check-sentinel.py <file-or-dir>", file=sys.stderr)
        return 2
    result = check_sentinel(sys.argv[1])
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
