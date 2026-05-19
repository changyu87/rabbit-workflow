#!/usr/bin/env python3
"""test-rabbit-print-messages-schema.py — validate rabbit-print-messages.json
against rabbit-print.schema.json and assert the required shape declared in
Inv 34 (registry data file).

End-to-end: loads the on-disk registry and schema files; performs minimal
JSON-Schema-style structural validation (no third-party dependency); then
asserts the ten required message-ids, the brand string, the bar string,
and the per-message field shapes. Also asserts that the previously-required
'r1-branch' id is absent (removed alongside rabbit-cage Inv 61).
"""

import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "schemas"))
MESSAGES_FILE = os.path.join(SCHEMAS_DIR, "rabbit-print-messages.json")
SCHEMA_FILE = os.path.join(SCHEMAS_DIR, "rabbit-print.schema.json")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


REQUIRED_IDS = {
    "welcome", "policy-drift", "surface-drift",
    "scope-guard-off", "scope-guard-bypassed", "human-approval-bypass",
    "skills-updated", "policy-refreshed", "tdd-transition", "tdd-forced",
}
# Explicitly removed alongside rabbit-cage Inv 61 (the R1 hook). The id MUST
# NOT reappear without a new spec change.
REMOVED_IDS = {"r1-branch"}


def validate(instance, schema, path="$"):
    """Minimal JSON-Schema-ish validator covering the features we use:
    type, required, properties, additionalProperties, enum, minLength.
    Returns list of error strings; empty list = valid."""
    errors = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(instance, dict):
            errors.append(f"{path}: expected object, got {type(instance).__name__}")
            return errors
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required key {req!r}")
        props = schema.get("properties", {})
        for key, val in instance.items():
            if key in props:
                errors.extend(validate(val, props[key], f"{path}.{key}"))
            else:
                addl = schema.get("additionalProperties")
                if addl is False:
                    errors.append(f"{path}: additional property {key!r} not allowed")
                elif isinstance(addl, dict):
                    errors.extend(validate(val, addl, f"{path}.{key}"))
    elif t == "string":
        if not isinstance(instance, str):
            errors.append(f"{path}: expected string, got {type(instance).__name__}")
            return errors
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: string shorter than minLength {schema['minLength']}")
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{path}: value {instance!r} not in enum {schema['enum']}")
    return errors


# t1: both files exist
if os.path.isfile(MESSAGES_FILE):
    ok("t1: rabbit-print-messages.json exists")
else:
    fail(f"t1: rabbit-print-messages.json missing at {MESSAGES_FILE}")

if os.path.isfile(SCHEMA_FILE):
    ok("t1b: rabbit-print.schema.json exists")
else:
    fail(f"t1b: rabbit-print.schema.json missing at {SCHEMA_FILE}")

messages = None
schema = None
if os.path.isfile(MESSAGES_FILE) and os.path.isfile(SCHEMA_FILE):
    try:
        with open(MESSAGES_FILE) as f:
            messages = json.load(f)
        ok("t2: rabbit-print-messages.json is valid JSON")
    except (json.JSONDecodeError, OSError) as e:
        fail(f"t2: rabbit-print-messages.json not valid JSON: {e}")
    try:
        with open(SCHEMA_FILE) as f:
            schema = json.load(f)
        ok("t2b: rabbit-print.schema.json is valid JSON")
    except (json.JSONDecodeError, OSError) as e:
        fail(f"t2b: rabbit-print.schema.json not valid JSON: {e}")

# t3: messages file validates against schema
if messages is not None and schema is not None:
    errs = validate(messages, schema)
    if errs:
        for e in errs:
            fail(f"t3: schema validation: {e}")
    else:
        ok("t3: rabbit-print-messages.json validates against rabbit-print.schema.json")

# t4: brand and bar are exact strings
if messages is not None:
    if messages.get("brand") == "[\U0001f407 rabbit \U0001f407]":
        ok("t4: brand is exactly '[🐇 rabbit 🐇]'")
    else:
        fail(f"t4: brand mismatch: got {messages.get('brand')!r}")
    if messages.get("bar") == "━━━":
        ok("t4b: bar is exactly '━━━'")
    else:
        fail(f"t4b: bar mismatch: got {messages.get('bar')!r}")

# t5: required colors green and red
if messages is not None:
    colors = messages.get("colors", {})
    for col in ("green", "red"):
        if col in colors and "ansi" in colors[col] and "reset" in colors[col]:
            ok(f"t5: colors.{col} present with ansi/reset")
        else:
            fail(f"t5: colors.{col} missing or missing ansi/reset")

# t6: all 10 required message-ids present
if messages is not None:
    msgs = messages.get("messages", {})
    missing = REQUIRED_IDS - set(msgs.keys())
    if missing:
        fail(f"t6: missing message-ids: {sorted(missing)}")
    else:
        ok("t6: all 10 required message-ids present")

# t6b: removed message-ids MUST be absent (Inv 34 — r1-branch was removed
# alongside the rabbit-cage R1 enforcement hook).
if messages is not None:
    msgs = messages.get("messages", {})
    leaked = REMOVED_IDS & set(msgs.keys())
    if leaked:
        fail(f"t6b: removed message-ids still present: {sorted(leaked)}")
    else:
        ok("t6b: removed message-ids absent (r1-branch)")

# t7: each required message has icon, color, text and color in {green,red}
if messages is not None:
    msgs = messages.get("messages", {})
    for mid in REQUIRED_IDS:
        if mid not in msgs:
            continue
        m = msgs[mid]
        if not isinstance(m, dict):
            fail(f"t7: messages.{mid} not an object")
            continue
        for fld in ("icon", "color", "text"):
            if fld not in m or not isinstance(m[fld], str) or not m[fld]:
                fail(f"t7: messages.{mid}.{fld} missing or empty")
                break
        else:
            if m["color"] not in ("green", "red"):
                fail(f"t7: messages.{mid}.color={m['color']!r} not green/red")
            else:
                ok(f"t7: messages.{mid} has icon/color/text; color={m['color']}")

# t7b: surface-drift text MUST contain the {files} placeholder (Inv 35(d),
# BACKLOG-21). The named wrapper surface_drift(files: str) substitutes this
# placeholder; an empty/missing placeholder would silently allow callers to
# emit an empty file list.
if messages is not None:
    msgs = messages.get("messages", {})
    sd = msgs.get("surface-drift", {})
    if "{files}" in sd.get("text", ""):
        ok("t7b: surface-drift text contains '{files}' placeholder")
    else:
        fail(f"t7b: surface-drift text missing '{{files}}' placeholder: {sd.get('text')!r}")

# t8: top-level metadata fields present (schema-as-artifact)
if messages is not None:
    for fld in ("schema_version", "owner", "deprecation_criterion"):
        if fld in messages and messages[fld]:
            ok(f"t8: registry has {fld}")
        else:
            fail(f"t8: registry missing {fld}")

if schema is not None:
    for fld in ("schema_version", "owner", "deprecation_criterion"):
        if fld in schema and schema[fld]:
            ok(f"t8b: schema doc has {fld}")
        else:
            fail(f"t8b: schema doc missing {fld}")

if FAIL != 0:
    print("test-rabbit-print-messages-schema: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-rabbit-print-messages-schema: all checks passed.")
