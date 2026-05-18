#!/usr/bin/env python3
"""check-template-schema-producer-consistency.py — validate that bug-template.json
top-level keys are a subset of the live producer field set.

The producer set is the union of fields written by the current rabbit-file
item producers (now consolidated under the bug-backlog-files branch). Legacy
shell producers were removed; this script references only live producers
(see Inv 23).

Usage:
  python3 check-template-schema-producer-consistency.py <template-path>

Exit:  0 template keys are consistent; 1 unknown key(s) found; 2 invocation error.

Version: 1.1.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when template/producer consistency is enforced by a schema registry.
"""

import json
import sys

# Live producer field set — fields that any current producer of a bug item
# may write. Derived from the rabbit-file bug-item producers; kept in sync
# with bug.json.schema.json.
PRODUCER_FIELDS = {
    "name", "title", "status", "severity", "description", "related_feature",
    "filed", "filed_by", "closed", "closed_by", "history"
}

# Template metadata keys (allowed at the top level of any template).
TEMPLATE_METADATA = {"template_version"}


def main():
    if len(sys.argv) != 2:
        print("usage: check-template-schema-producer-consistency.py <template-path>", file=sys.stderr)
        sys.exit(2)

    template_path = sys.argv[1]

    try:
        with open(template_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: failed to parse {template_path}: {e}", file=sys.stderr)
        sys.exit(2)

    fail = False
    for k in data.keys():
        if k in TEMPLATE_METADATA:
            continue
        if k not in PRODUCER_FIELDS:
            print(f"UNKNOWN KEY: '{k}' in bug-template.json is not in the producer field set",
                  file=sys.stderr)
            fail = True

    if fail:
        print("FAIL: template-schema-producer consistency check failed", file=sys.stderr)
        sys.exit(1)

    print("OK: all bug-template.json keys are consistent with the live producer field set")
    sys.exit(0)


if __name__ == '__main__':
    main()
