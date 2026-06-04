#!/usr/bin/env python3
"""test-feature-json-schema-admits-meta-contract.py — verifies that
feature.json.schema.json declares optional properties for manifest, runtime,
configuration, and prompts referencing the four meta-contract schemas
(Inv 35, Inv 44).
"""

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas/feature.json.schema.json")

EXPECTED_REFS = {
    "manifest": "manifest.schema.json",
    "runtime": "runtime.schema.json",
    "configuration": "configuration.schema.json",
    "prompts": "prompts.schema.json",
}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


if not os.path.isfile(SCHEMA_PATH):
    fail(f"schema file missing: {SCHEMA_PATH}")
    sys.exit(1)

with open(SCHEMA_PATH) as f:
    try:
        schema = json.load(f)
    except json.JSONDecodeError as e:
        fail(f"not valid JSON: {e}")
        sys.exit(1)

props = schema.get("properties", {})
for key, expected_ref in EXPECTED_REFS.items():
    if key not in props:
        fail(f"feature.json.schema.json missing property '{key}'")
        continue
    ref = props[key].get("$ref")
    if ref != expected_ref:
        fail(f"property '{key}' must $ref '{expected_ref}', got {ref!r}")
    else:
        ok(f"property '{key}' references '{expected_ref}'")

# None of the three must be in required (they're optional per design)
required = set(schema.get("required", []))
for key in EXPECTED_REFS:
    if key in required:
        fail(f"property '{key}' must be OPTIONAL (not in required[]), but is in required")
    else:
        ok(f"property '{key}' is optional (not in required[])")

if FAIL:
    print("test-feature-json-schema-admits-meta-contract: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-feature-json-schema-admits-meta-contract: all checks passed.")
