#!/usr/bin/env python3
"""test-workspace-structure-naming.py — Inv 33.

workspace-structure.json schema field naming MUST be internally consistent:
all snake_case (no mixed camelCase keys).
"""

import os
import sys
import json
import re

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA = os.path.join(FEATURE_DIR, "schemas/workspace-structure.json")

FAIL = 0

with open(SCHEMA) as f:
    schema = json.load(f)

camel_re = re.compile(r'[a-z][A-Z]')

def walk(node, path=""):
    """Walk JSON schema; flag camelCase top-level metadata keys."""
    fails = []
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and camel_re.search(k):
                # Allow JSON Schema reserved keys like $schema, $id, $ref, additionalProperties, oneOf, minLength
                # The standard reserved keys we tolerate:
                reserved = {"$schema", "$id", "$ref", "additionalProperties", "minLength",
                            "maxLength", "oneOf", "anyOf", "allOf", "patternProperties",
                            "minItems", "maxItems", "uniqueItems", "exclusiveMinimum",
                            "exclusiveMaximum", "multipleOf", "minProperties", "maxProperties"}
                if k in reserved:
                    continue
                fails.append(f"{path}.{k}" if path else k)
            fails.extend(walk(v, f"{path}.{k}" if path else k))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            fails.extend(walk(item, f"{path}[{i}]"))
    return fails

bad = walk(schema)
if bad:
    for b in bad:
        print(f"FAIL: camelCase key '{b}' in workspace-structure.json", file=sys.stderr)
    FAIL = 1
else:
    print("PASS: all keys in workspace-structure.json are snake_case (or JSON Schema reserved)")

if FAIL:
    print("test-workspace-structure-naming: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-workspace-structure-naming: all checks passed.")
