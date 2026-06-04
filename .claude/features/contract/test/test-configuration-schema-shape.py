#!/usr/bin/env python3
"""test-configuration-schema-shape.py — validates configuration.schema.json
shape: top-level array of configurable declarations; each requires id +
subcommand; mutation API enum is closed; storage type enum is closed;
each item must declare exactly one of `values` or `actions` (oneOf).
Also verifies spec-rules.md ownership metadata.
"""

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas/configuration.schema.json")

EXPECTED_STORAGE_TYPES = {"marker-file", "json-key", "json-array", "json-array-templated"}

EXPECTED_MUTATION_APIS = {
    "write_marker",
    "delete_marker",
    "set_json_key",
    "delete_json_key",
    "append_json_array",
    "remove_json_array_value",
    "run_feature_script",
}

EXPECTED_COLORS = {"red", "green", "yellow"}

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
ok("configuration.schema.json parses as JSON")

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
if not {"id", "subcommand"}.issubset(required):
    fail(f"items.required must include id and subcommand, got {sorted(required)}")
else:
    ok("items.required includes id and subcommand")

storage = items.get("properties", {}).get("storage", {})
storage_type_enum = set(storage.get("properties", {}).get("type", {}).get("enum", []))
if storage_type_enum != EXPECTED_STORAGE_TYPES:
    fail(f"storage.type enum mismatch — got {sorted(storage_type_enum)}")
else:
    ok("storage.type enum is the closed storage vocabulary")

values_prop = items.get("properties", {}).get("values", {})
api_call_ref = values_prop.get("additionalProperties", {}).get("$ref")
if api_call_ref != "#/definitions/api_call":
    fail(f"values.additionalProperties must $ref api_call, got {api_call_ref!r}")
else:
    ok("values references api_call definition")

actions_prop = items.get("properties", {}).get("actions", {})
actions_ref = actions_prop.get("additionalProperties", {}).get("$ref")
if actions_ref != "#/definitions/api_call":
    fail(f"actions.additionalProperties must $ref api_call, got {actions_ref!r}")
else:
    ok("actions references api_call definition")

api_call = schema.get("definitions", {}).get("api_call", {})
api_enum = set(api_call.get("properties", {}).get("api", {}).get("enum", []))
if api_enum != EXPECTED_MUTATION_APIS:
    missing = EXPECTED_MUTATION_APIS - api_enum
    extra = api_enum - EXPECTED_MUTATION_APIS
    fail(f"mutation api enum mismatch — missing: {sorted(missing)}, extra: {sorted(extra)}")
else:
    ok("mutation api enum is the closed mutation API set")

if api_call.get("additionalProperties") is not False:
    fail("api_call.additionalProperties must be false (closed shape)")
else:
    ok("api_call.additionalProperties is false")

one_of = items.get("oneOf", [])
required_sets = [frozenset(o.get("required", [])) for o in one_of]
if frozenset(["values"]) not in required_sets or frozenset(["actions"]) not in required_sets:
    fail(f"items.oneOf must require [values] xor [actions], got {required_sets}")
else:
    ok("items.oneOf enforces exactly one of values/actions")

alert_msg = items.get("properties", {}).get("alert-message", {})
color_enum = set(alert_msg.get("properties", {}).get("color", {}).get("enum", []))
if color_enum != EXPECTED_COLORS:
    fail(f"alert-message.color enum must be {sorted(EXPECTED_COLORS)}, got {sorted(color_enum)}")
else:
    ok("alert-message.color enum is the closed color set")

# --- phase 3 of #733: additive per-feature command + restart manifestation ---

props = items.get("properties", {})

# The entry stays closed (additionalProperties false) so additions are explicit.
if items.get("additionalProperties") is not False:
    fail("items.additionalProperties must stay false (closed entry shape)")
else:
    ok("items.additionalProperties stays false")

command_prop = props.get("command")
if not isinstance(command_prop, dict) or command_prop.get("type") != "string":
    fail(f"optional `command` property must be a declared string, got {command_prop!r}")
elif "command" in required:
    fail("`command` must be OPTIONAL (not in items.required)")
else:
    ok("optional `command` property declared (per-feature command name)")

restart_prop = props.get("restart_required")
if not isinstance(restart_prop, dict) or restart_prop.get("type") != "boolean":
    fail(f"optional `restart_required` property must be a declared boolean, got {restart_prop!r}")
elif "restart_required" in required:
    fail("`restart_required` must be OPTIONAL (not in items.required)")
else:
    ok("optional `restart_required` property declared (boolean)")


def validate_entry(entry):
    """Minimal hand-rolled validator: required keys present; no key outside the
    declared properties (additionalProperties false); types of the two new
    optional fields when present. Mirrors the existing stdlib-only pattern.
    """
    errs = []
    for r in required:
        if r not in entry:
            errs.append(f"missing required key {r!r}")
    if not (("values" in entry) ^ ("actions" in entry)):
        errs.append("must declare exactly one of values/actions")
    for k in entry:
        if k not in props:
            errs.append(f"unknown property {k!r} (additionalProperties false)")
    if "command" in entry and not isinstance(entry["command"], str):
        errs.append("command must be a string")
    if "restart_required" in entry and not isinstance(entry["restart_required"], bool):
        errs.append("restart_required must be a boolean")
    return errs


# An entry carrying the two new fields validates.
with_new = {
    "id": "tdd-autonomous",
    "subcommand": "tdd-autonomous",
    "command": "rabbit-tdd-autonomous",
    "restart_required": True,
    "values": {"true": {"api": "write_marker", "args": {}}},
}
e = validate_entry(with_new)
if e:
    fail(f"entry WITH new fields should validate: {e}")
else:
    ok("entry carrying command + restart_required validates")

# An existing-style entry WITHOUT the new fields still validates (coexistence).
without_new = {
    "id": "scope-guard",
    "subcommand": "scope-guard",
    "values": {"true": {"api": "delete_marker", "args": {}}},
}
e = validate_entry(without_new)
if e:
    fail(f"entry WITHOUT new fields should still validate (coexistence): {e}")
else:
    ok("entry without new fields still validates (rabbit-config coexistence)")

if FAIL:
    print("test-configuration-schema-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-configuration-schema-shape: all checks passed.")
