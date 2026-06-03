#!/usr/bin/env python3
"""test-runtime-schema-shape.py — validates runtime.schema.json shape:
top-level object keyed by Claude Code event names, each value an array of
{api, args} objects against the closed runtime API enum. Also verifies
spec-rules.md ownership metadata (schema_version, owner, deprecation_criterion).
"""

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas/runtime.schema.json")

EXPECTED_EVENTS = {"Stop", "SessionStart", "UserPromptSubmit", "PreToolUse"}

EXPECTED_RUNTIME_APIS = {
    "check_drift_regenerate",
    "check_manifest_drift",
    "check_marker_alert",
    "check_marker_consume_alert",
    "check_counter_threshold_refresh",
    "welcome_with_policy",
    "iterate_configurables_alerts",
    "iterate_configurables_banner",
    "check_prompt_injection_failures",
    "cleanup_old_prompts",
    "write_mode_marker",
    "check_release_update",
    "emit_auto_evolve_banner",
    "emit_auto_evolve_stop_line",
    "emit_stop_timestamp",
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
ok("runtime.schema.json parses as JSON")

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

if schema.get("type") != "object":
    fail(f"top-level type must be 'object', got {schema.get('type')!r}")
else:
    ok("top-level type is object")

if schema.get("additionalProperties") is not False:
    fail("top-level additionalProperties must be false (closed event set)")
else:
    ok("top-level additionalProperties is false")

props = schema.get("properties", {})
event_keys = set(props.keys())
if event_keys != EXPECTED_EVENTS:
    missing = EXPECTED_EVENTS - event_keys
    extra = event_keys - EXPECTED_EVENTS
    fail(f"event keys mismatch — missing: {sorted(missing)}, extra: {sorted(extra)}")
else:
    ok("event keys are the closed Claude Code event set")

call_list = schema.get("definitions", {}).get("call_list", {})
if call_list.get("type") != "array":
    fail("definitions.call_list.type must be 'array'")
else:
    ok("definitions.call_list is array")

items = call_list.get("items", {})
required = set(items.get("required", []))
if required != {"api", "args"}:
    fail(f"call_list.items.required must be ['api', 'args'], got {sorted(required)}")
else:
    ok("call_list.items.required is [api, args]")

if items.get("additionalProperties") is not False:
    fail("call_list.items.additionalProperties must be false")
else:
    ok("call_list.items.additionalProperties is false")

api_prop = items.get("properties", {}).get("api", {})
api_enum = set(api_prop.get("enum", []))
if api_enum != EXPECTED_RUNTIME_APIS:
    missing = EXPECTED_RUNTIME_APIS - api_enum
    extra = api_enum - EXPECTED_RUNTIME_APIS
    fail(f"runtime api enum mismatch — missing: {sorted(missing)}, extra: {sorted(extra)}")
else:
    ok("api enum is the closed runtime API set")

for ev in EXPECTED_EVENTS:
    ref = props.get(ev, {}).get("$ref")
    if ref != "#/definitions/call_list":
        fail(f"event '{ev}' must $ref #/definitions/call_list, got {ref!r}")
    else:
        ok(f"event '{ev}' references call_list")

args_prop = items.get("properties", {}).get("args", {})
if args_prop.get("type") != "object":
    fail("args.type must be 'object'")
else:
    ok("call_list.items.args.type is object")

if FAIL:
    print("test-runtime-schema-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-schema-shape: all checks passed.")
