#!/usr/bin/env python3
"""test-manifest-schema-shape.py — validates the structural shape of
manifest.schema.json: it must be valid JSON, declare itself as a JSON Schema
draft-07 document, describe an array of {api, args} objects, and enumerate
the closed publish API set.
"""

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas/manifest.schema.json")

EXPECTED_PUBLISH_APIS = {
    "publish_skill",
    "publish_command",
    "publish_agent",
    "publish_hook",
    "publish_settings",
    "publish_file",
    "publish_generated",
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
ok("manifest.schema.json parses as JSON")

if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
    fail("$schema is not draft-07")
else:
    ok("$schema declares draft-07")

if schema.get("type") != "array":
    fail(f"top-level type must be 'array', got {schema.get('type')!r}")
else:
    ok("top-level type is array")

items = schema.get("items", {})
if items.get("type") != "object":
    fail("items.type must be 'object'")
else:
    ok("items.type is object")

required = set(items.get("required", []))
if required != {"api", "args"}:
    fail(f"items.required must be ['api', 'args'], got {sorted(required)}")
else:
    ok("items.required is [api, args]")

if items.get("additionalProperties") is not False:
    fail("items.additionalProperties must be false (closed shape)")
else:
    ok("items.additionalProperties is false")

api_prop = items.get("properties", {}).get("api", {})
api_enum = set(api_prop.get("enum", []))
if api_enum != EXPECTED_PUBLISH_APIS:
    missing = EXPECTED_PUBLISH_APIS - api_enum
    extra = api_enum - EXPECTED_PUBLISH_APIS
    fail(f"api enum mismatch — missing: {sorted(missing)}, extra: {sorted(extra)}")
else:
    ok("api enum is the closed publish API set")

args_prop = items.get("properties", {}).get("args", {})
if args_prop.get("type") != "object":
    fail("args.type must be 'object'")
else:
    ok("args.type is object")

if FAIL:
    print("test-manifest-schema-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-manifest-schema-shape: all checks passed.")
