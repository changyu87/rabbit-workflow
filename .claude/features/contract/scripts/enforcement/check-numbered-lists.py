#!/usr/bin/env python3
"""check-numbered-lists.py — thin CLI shim around
contract.lib.checks.check_numbered_lists (spec Inv 26, Inv 29).

Usage: check-numbered-lists.py <path> [<path> ...]
Exit:  0 no violations; 1 violations found; 2 invocation error.

Each <path> may be a .md file or a directory. Out-of-scope subtrees
(/archive/, /docs/superpowers/) are skipped during directory walks.

Version: 2.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when superseded by a generalized Markdown style linter.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_numbered_lists  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "ERROR: usage: check-numbered-lists.py <path> [<path> ...]",
            file=sys.stderr,
        )
        return 2
    result = check_numbered_lists(sys.argv[1:])
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
