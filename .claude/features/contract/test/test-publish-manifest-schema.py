#!/usr/bin/env python3
"""test-publish-manifest-schema.py — validates publish-manifest.schema.json.

t1: schema file exists
t2: schema is valid JSON
t3: ownership fields present (schema_version, owner, deprecation_criterion)
t4: title == 'publish-manifest'
"""
import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "publish-manifest.schema.json")

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def fail_t(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    failed += 1


print("test-publish-manifest-schema.py")

if os.path.isfile(SCHEMA_PATH):
    ok(1, "publish-manifest.schema.json exists")
else:
    fail_t(1, f"publish-manifest.schema.json missing at {SCHEMA_PATH}")

schema = None
if os.path.isfile(SCHEMA_PATH):
    try:
        schema = json.load(open(SCHEMA_PATH))
        ok(2, "schema is valid JSON")
    except json.JSONDecodeError as e:
        fail_t(2, f"schema is not valid JSON: {e}")
else:
    fail_t(2, "schema is not valid JSON (file missing)")

if schema is not None:
    for field in ("schema_version", "owner", "deprecation_criterion"):
        if field in schema:
            ok(3, f"ownership field '{field}' present")
        else:
            fail_t(3, f"ownership field '{field}' missing")
else:
    fail_t(3, "ownership fields not checked (schema missing/invalid)")

if schema is not None:
    if schema.get("title") == "publish-manifest":
        ok(4, "title == 'publish-manifest'")
    else:
        fail_t(4, f"title is {schema.get('title')!r}, expected 'publish-manifest'")
else:
    fail_t(4, "title not checked (schema missing/invalid)")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
