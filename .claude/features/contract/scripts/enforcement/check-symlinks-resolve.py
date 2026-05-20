#!/usr/bin/env python3
"""check-symlinks-resolve.py — thin CLI shim around
contract.lib.checks.check_symlinks_resolve (spec Inv 30, Inv 44).

Usage: check-symlinks-resolve.py [repo-root]
Exit:  0 all symlinks resolve; 1 dangling found; 2 invocation error.

Version: 2.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when symlink validation is provided by a native linter.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_symlinks_resolve, _get_repo_root  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        repo_root = sys.argv[1]
    else:
        repo_root = _get_repo_root()
    if not repo_root:
        print("ERROR: cannot determine repo root", file=sys.stderr)
        return 2
    result = check_symlinks_resolve(repo_root)
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
