#!/usr/bin/env python3
# test-schemas-valid-json.py — verify all schema files are valid JSON.

import os
import sys
import json
import glob

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMAS_DIR = os.path.join(FEATURE_DIR, "schemas")
FAIL = 0

for schema in glob.glob(os.path.join(SCHEMAS_DIR, "*.json")):
    if not os.path.isfile(schema):
        continue
    try:
        json.load(open(schema))
    except (json.JSONDecodeError, OSError) as e:
        print(f"FAIL: invalid JSON: {schema}", file=sys.stderr)
        FAIL = 1

if FAIL != 0:
    print("test-schemas-valid-json: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-schemas-valid-json: all schema files are valid JSON.")
