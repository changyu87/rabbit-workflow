#!/usr/bin/env python3
"""test-feature-schema-permissive.py — Inv 18.

feature.json.schema.json MUST NOT require `bugs_root` and MUST permit the
optional top-level `updated` field. Validate every real feature.json in the
repo passes the schema (end-to-end).
"""

import os
import sys
import json
import glob

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA = os.path.join(FEATURE_DIR, "schemas/feature.json.schema.json")

FAIL = 0

with open(SCHEMA) as f:
    schema = json.load(f)

# t1: bugs_root MUST NOT be in required
required = schema.get("required", [])
if "bugs_root" in required:
    print(f"FAIL t1: 'bugs_root' is in required (got {required})", file=sys.stderr)
    FAIL = 1
else:
    print("PASS t1: 'bugs_root' is not required")

# t2: 'updated' MUST be allowed (either in properties or additionalProperties: true)
props = schema.get("properties", {})
allow_additional = schema.get("additionalProperties", True)
if "updated" in props or allow_additional:
    print("PASS t2: 'updated' is permitted by schema")
else:
    print("FAIL t2: schema does not permit 'updated' (not in properties and additionalProperties is false)", file=sys.stderr)
    FAIL = 1

# t3 (end-to-end): every real feature.json validates against schema
try:
    import jsonschema
    have_jsonschema = True
except ImportError:
    have_jsonschema = False

if have_jsonschema:
    validator = jsonschema.Draft7Validator(schema)
    feature_jsons = sorted(glob.glob(os.path.join(REPO_ROOT, ".claude/features/*/feature.json")))
    if not feature_jsons:
        print("FAIL t3: no feature.json files found to validate", file=sys.stderr)
        FAIL = 1
    for fj in feature_jsons:
        with open(fj) as f:
            data = json.load(f)
        errors = list(validator.iter_errors(data))
        if errors:
            print(f"FAIL t3: {fj}: {[e.message for e in errors]}", file=sys.stderr)
            FAIL = 1
        else:
            print(f"PASS t3: {os.path.relpath(fj, REPO_ROOT)} validates")
else:
    # Manual minimal check: each feature.json must have all `required` keys and no key in `additionalProperties: false` mode that's not declared.
    feature_jsons = sorted(glob.glob(os.path.join(REPO_ROOT, ".claude/features/*/feature.json")))
    for fj in feature_jsons:
        with open(fj) as f:
            data = json.load(f)
        # Required fields present?
        for req in required:
            if req not in data:
                print(f"FAIL t3: {fj}: missing required '{req}'", file=sys.stderr)
                FAIL = 1
        # additionalProperties false?
        if schema.get("additionalProperties") is False:
            for k in data.keys():
                if k not in props:
                    print(f"FAIL t3: {fj}: extra key '{k}' not in schema properties", file=sys.stderr)
                    FAIL = 1
        if not any(req not in data for req in required):
            print(f"PASS t3: {os.path.relpath(fj, REPO_ROOT)} validates (manual)")

if FAIL:
    print("test-feature-schema-permissive: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-feature-schema-permissive: all checks passed.")
