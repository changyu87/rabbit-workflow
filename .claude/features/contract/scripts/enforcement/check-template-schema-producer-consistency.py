#!/usr/bin/env python3
"""check-template-schema-producer-consistency.py — thin CLI shim around
contract.lib.checks.check_template_producer_consistency (spec Inv 19, Inv 37).

Usage: check-template-schema-producer-consistency.py <template-path>
Exit:  0 consistent; 1 unknown key(s); 2 invocation error.

Version: 2.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when template/producer consistency is enforced by a schema registry.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
from lib.checks import check_template_producer_consistency  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: check-template-schema-producer-consistency.py <template-path>",
            file=sys.stderr,
        )
        return 2
    result = check_template_producer_consistency(sys.argv[1])
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
