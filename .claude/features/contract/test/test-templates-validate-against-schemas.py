#!/usr/bin/env python3
"""test-templates-validate-against-schemas.py — CONTRACT-BUG-48 / Inv 50.

Every <X>-template.json under templates/ MUST validate against its sibling
<X>.schema.json (or <X>.json.schema.json) under schemas/ — except for
pattern constraints, which templates intentionally violate via placeholder
strings like {{version}}. Coverage:

  t1: project-map-template.json validates against project-map.json.schema.json
  t2: feature-json-template.json validates against feature.json.schema.json
      (redundant with Inv 19 but kept for cross-template consistency)

Hand-rolled stdlib validation (no jsonschema dep) matching the pattern in
test-project-map-schema-shape.py. Pattern checks are intentionally skipped
because template placeholders (e.g. {{version}}) cannot match e.g. a semver
regex; structural shape is what this test enforces.
"""

import json
import os
import re
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
SCHEMAS_DIR = os.path.join(FEATURE_DIR, "schemas")
TEMPLATES_DIR = os.path.join(FEATURE_DIR, "templates")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def validate(doc, sch):
    """Hand-rolled subset validator. Skips pattern checks (templates carry
    placeholder values that intentionally don't match patterns). Returns
    list of error strings; empty = valid."""
    errs = []
    t = sch.get("type")
    if t == "object":
        if not isinstance(doc, dict):
            errs.append(f"expected object, got {type(doc).__name__}")
            return errs
        for req in sch.get("required", []):
            if req not in doc:
                errs.append(f"missing required property: {req}")
        sch_props = sch.get("properties", {})
        pattern_props = sch.get("patternProperties", {})
        additional = sch.get("additionalProperties", True)
        for key, val in doc.items():
            if key in sch_props:
                errs.extend(f"{key}: {e}" for e in validate(val, sch_props[key]))
            else:
                matched = False
                for pat, psch in pattern_props.items():
                    if re.search(pat, key):
                        matched = True
                        errs.extend(f"{key}: {e}" for e in validate(val, psch))
                        break
                if not matched and additional is False:
                    errs.append(f"unexpected property: {key}")
    elif t == "string":
        if not isinstance(doc, str):
            errs.append(f"expected string, got {type(doc).__name__}")
        # NOTE: pattern check intentionally skipped — templates may carry
        # placeholder strings like "{{version}}" that don't match e.g. semver.
    elif t == "array":
        if not isinstance(doc, list):
            errs.append(f"expected array, got {type(doc).__name__}")
            return errs
        item_sch = sch.get("items")
        if item_sch:
            for i, item in enumerate(doc):
                errs.extend(f"[{i}]: {e}" for e in validate(item, item_sch))
    return errs


def check_template_schema_pair(test_id, template_basename, schema_basename):
    template_path = os.path.join(TEMPLATES_DIR, template_basename)
    schema_path = os.path.join(SCHEMAS_DIR, schema_basename)
    if not os.path.isfile(template_path):
        fail(test_id, f"template missing: {template_path}")
        return
    if not os.path.isfile(schema_path):
        fail(test_id, f"schema missing: {schema_path}")
        return
    with open(template_path) as f:
        template = json.load(f)
    with open(schema_path) as f:
        schema = json.load(f)
    errs = validate(template, schema)
    if errs:
        fail(test_id, f"{template_basename} does not validate against {schema_basename}: {errs}")
    else:
        ok(test_id, f"{template_basename} validates against {schema_basename}")


# t1: project-map-template.json validates against project-map.json.schema.json
check_template_schema_pair(
    "t1",
    "project-map-template.json",
    "project-map.json.schema.json",
)

# t2: feature-json-template.json validates against feature.json.schema.json
# (redundant with Inv 19's test-feature-template-validates-schema.py but
# asserted here for cross-template consistency of Inv 50).
check_template_schema_pair(
    "t2",
    "feature-json-template.json",
    "feature.json.schema.json",
)

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
