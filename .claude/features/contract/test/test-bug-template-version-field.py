#!/usr/bin/env python3
"""test-bug-template-version-field.py — Inv 25.

bug-template.json MUST use the field name `template_version` (not the legacy
underscore-prefixed `_template_version`).
"""

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TEMPLATE = os.path.join(FEATURE_DIR, "templates/bug-template.json")

FAIL = 0

with open(TEMPLATE) as f:
    data = json.load(f)

if "_template_version" in data:
    print("FAIL t1: bug-template.json still uses legacy '_template_version'", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: bug-template.json does not use '_template_version'")

if "template_version" not in data:
    print("FAIL t2: bug-template.json missing 'template_version'", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t2: bug-template.json has 'template_version'")

if FAIL:
    print("test-bug-template-version-field: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-bug-template-version-field: all checks passed.")
