#!/usr/bin/env python3
# check-template-schema-producer-consistency.py — validate that bug-template.json
# top-level keys (excluding _template_version) are a subset of what file-bug.sh
# actually writes.
#
# Known producer set (fields written by file-bug.sh):
#   name, title, status, severity, description, related_feature,
#   filed, filed_by, closed, closed_by, history
#
# Usage (invoked by check-template-schema-producer-consistency.sh):
#   python3 check-template-schema-producer-consistency.py <template-path>
#
# Exit:  0 template keys are consistent; 1 unknown key(s) found; 2 invocation error.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when template/producer consistency is enforced by a schema registry.

import json
import sys

PRODUCER_FIELDS = {
    "name", "title", "status", "severity", "description", "related_feature",
    "filed", "filed_by", "closed", "closed_by", "history"
}


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
        if k == '_template_version':
            continue
        if k not in PRODUCER_FIELDS:
            print(f"UNKNOWN KEY: '{k}' in bug-template.json is not in the file-bug.sh producer set",
                  file=sys.stderr)
            fail = True

    if fail:
        print("FAIL: template-schema-producer consistency check failed", file=sys.stderr)
        sys.exit(1)

    print("OK: all bug-template.json keys are consistent with file-bug.sh producer set")
    sys.exit(0)


if __name__ == '__main__':
    main()
