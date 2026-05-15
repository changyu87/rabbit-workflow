#!/usr/bin/env python3
# test-rabbit-print-schema.py — tests for rabbit-print.schema.json

import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.join(SCRIPT_DIR, "../schemas")
SCHEMA_FILE = os.path.join(SCHEMAS_DIR, "rabbit-print.schema.json")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


# t1: schema file exists
if os.path.isfile(SCHEMA_FILE):
    ok("t1: rabbit-print.schema.json exists")
else:
    fail(f"t1: rabbit-print.schema.json missing at {SCHEMA_FILE}")

# t2: schema is valid JSON
schema_data = None
if os.path.isfile(SCHEMA_FILE):
    try:
        schema_data = json.load(open(SCHEMA_FILE))
        ok("t2: rabbit-print.schema.json is valid JSON")
    except (json.JSONDecodeError, OSError):
        fail("t2: rabbit-print.schema.json is not valid JSON")

# t3: schema has a "format" field describing the [rabbit] pattern
if schema_data is not None:
    if "format" in schema_data:
        ok("t3: schema has 'format' field")
    else:
        fail("t3: schema missing 'format' field")

# t4: schema has a "colors" field with "normal" and "alert" keys
if schema_data is not None:
    colors = schema_data.get("colors", {})
    if "normal" in colors and "alert" in colors:
        ok("t4: schema colors has 'normal' and 'alert' keys")
    else:
        fail("t4: schema colors missing 'normal' or 'alert'")

# t5: schema has a "version" field
if schema_data is not None:
    if "version" in schema_data:
        ok("t5: schema has 'version' field")
    else:
        fail("t5: schema missing 'version' field")

if FAIL != 0:
    print("test-rabbit-print-schema: FAIL")
    sys.exit(1)
print("test-rabbit-print-schema: all checks passed.")
