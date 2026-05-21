#!/usr/bin/env python3
"""check-naming.py — thin CLI shim around contract.lib.checks.check_naming
(spec Inv 10, Inv 15, Inv 37).

Banned prefixes (mirrored from the library): rbt-.

Usage:  check-naming.py [root]
Exit:   0 all conformant; 1 violations; 2 invocation error.

Version: 2.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when naming enforcement is provided by a native linter.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_naming  # noqa: E402


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = check_naming(root)
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
