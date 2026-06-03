#!/usr/bin/env python3
"""check-invariant-monotonic-order.py — thin CLI shim around
contract.lib.checks.check_invariant_monotonic_order (spec Inv 38, Inv 37).

Usage: check-invariant-monotonic-order.py <feature-dir> [<feature-dir> ...]
Exit:  0 no violations; 1 violations found; 2 invocation error.

Each <feature-dir> is a feature root containing spec.md, resolved through
the dual-read resolver in lib/checks.py (flat docs/spec.md preferred,
specs/spec.md fallback), so a feature on either layout is scanned identically.
Features in the library's KNOWN_ISSUES allowlist are skipped (pending renumber).

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when KNOWN_ISSUES is empty and the check is folded
into a generalized spec-numbering linter.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_invariant_monotonic_order  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "ERROR: usage: check-invariant-monotonic-order.py "
            "<feature-dir> [<feature-dir> ...]",
            file=sys.stderr,
        )
        return 2
    result = check_invariant_monotonic_order(sys.argv[1:])
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
