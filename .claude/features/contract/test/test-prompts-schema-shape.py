#!/usr/bin/env python3
"""test-prompts-schema-shape.py — validates the structural shape of
prompts.schema.json: it must be valid JSON, declare itself as a JSON Schema
draft-07 document, describe an array of {id, kind, inject, slots} objects
with closed shape, and enumerate the closed kind set (skill, subagent).

Per spec Inv 51.
"""

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas/prompts.schema.json")

EXPECTED_KINDS = {"skill", "subagent"}
EXPECTED_REQUIRED = {"id", "kind", "inject", "slots"}

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
ok("prompts.schema.json parses as JSON")

if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
    fail("$schema is not draft-07")
else:
    ok("$schema declares draft-07")

if not isinstance(schema.get("schema_version"), str) or not schema["schema_version"]:
    fail("schema_version is missing or empty (spec-rules.md requires it)")
else:
    ok("schema_version is present")

if not isinstance(schema.get("owner"), str) or not schema["owner"]:
    fail("owner is missing or empty (spec-rules.md requires it)")
else:
    ok("owner is present")

if not isinstance(schema.get("deprecation_criterion"), str) or not schema["deprecation_criterion"]:
    fail("deprecation_criterion is missing or empty (spec-rules.md requires it)")
else:
    ok("deprecation_criterion is present")

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
if required != EXPECTED_REQUIRED:
    fail(f"items.required must be {sorted(EXPECTED_REQUIRED)}, got {sorted(required)}")
else:
    ok(f"items.required is {sorted(EXPECTED_REQUIRED)}")

if items.get("additionalProperties") is not False:
    fail("items.additionalProperties must be false (closed shape)")
else:
    ok("items.additionalProperties is false")

item_props = items.get("properties", {})

id_prop = item_props.get("id", {})
if id_prop.get("type") != "string":
    fail("id.type must be 'string'")
else:
    ok("id.type is string")
if id_prop.get("pattern") != "^[a-z][a-z0-9-]*$":
    fail(f"id.pattern must be '^[a-z][a-z0-9-]*$', got {id_prop.get('pattern')!r}")
else:
    ok("id.pattern is '^[a-z][a-z0-9-]*$'")

kind_prop = item_props.get("kind", {})
if kind_prop.get("type") != "string":
    fail("kind.type must be 'string'")
else:
    ok("kind.type is string")
kind_enum = set(kind_prop.get("enum", []))
if kind_enum != EXPECTED_KINDS:
    fail(f"kind enum must be exactly {sorted(EXPECTED_KINDS)}, got {sorted(kind_enum)}")
else:
    ok("kind enum is the closed set [skill, subagent]")

inject_prop = item_props.get("inject", {})
if inject_prop.get("type") != "array":
    fail("inject.type must be 'array'")
else:
    ok("inject.type is array")
if inject_prop.get("minItems") != 1:
    fail(f"inject.minItems must be 1, got {inject_prop.get('minItems')!r}")
else:
    ok("inject.minItems is 1")
if inject_prop.get("items", {}).get("type") != "string":
    fail("inject.items.type must be 'string'")
else:
    ok("inject.items.type is string")

slots_prop = item_props.get("slots", {})
if slots_prop.get("type") != "array":
    fail("slots.type must be 'array'")
else:
    ok("slots.type is array")
slots_items = slots_prop.get("items", {})
if slots_items.get("type") != "string":
    fail("slots.items.type must be 'string'")
else:
    ok("slots.items.type is string")
if slots_items.get("pattern") != "^[a-z][a-z0-9_]*$":
    fail(f"slots.items.pattern must be '^[a-z][a-z0-9_]*$', got {slots_items.get('pattern')!r}")
else:
    ok("slots.items.pattern is '^[a-z][a-z0-9_]*$'")

if FAIL:
    print("test-prompts-schema-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-prompts-schema-shape: all checks passed.")
