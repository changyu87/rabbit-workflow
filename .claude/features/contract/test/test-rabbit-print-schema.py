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

# t6 (Inv 5 / BACKLOG-15): schema is the authoritative definition of the
# [rabbit] print format used by all rabbit-workflow hooks and CLI scripts.
# Every declared producer in schema['producers'] must (a) exist on disk and
# (b) reference '[rabbit]' in its source text. Absent producers, or producers
# that do not emit the [rabbit] prefix, contradict the authority claim.
if schema_data is not None:
    producers = schema_data.get("producers", [])
    repo_root = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
    missing = []
    no_prefix = []
    for p in producers:
        full = os.path.join(repo_root, p)
        if not os.path.isfile(full):
            missing.append(p)
            continue
        with open(full) as f:
            text = f.read()
        if "[rabbit]" not in text:
            no_prefix.append(p)
    if missing:
        fail(f"t6 (Inv 5): producers missing on disk: {missing}")
    if no_prefix:
        fail(f"t6 (Inv 5): producers do not emit the '[rabbit]' prefix: {no_prefix}")
    if not missing and not no_prefix:
        ok("t6 (Inv 5): rabbit-print schema is authoritative — every producer exists and emits '[rabbit]'")

if FAIL != 0:
    print("test-rabbit-print-schema: FAIL")
    sys.exit(1)
print("test-rabbit-print-schema: all checks passed.")
