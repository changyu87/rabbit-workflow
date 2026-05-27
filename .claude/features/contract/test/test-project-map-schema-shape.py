#!/usr/bin/env python3
"""test-project-map-schema-shape.py — validates the structural shape of
project-map.json.schema.json: it must be valid JSON, declare itself as a
JSON Schema draft-07 document, carry the spec-rules.md ownership-metadata
triple, and describe the {schema_version, features{<kebab-name>: {paths,
feature_dir}}} shape used by the plugin-mode project map.

Includes hand-rolled stdlib validation (no jsonschema dep) for a sample
valid project-map.json (t8) and three invalid documents (t9), matching the
pattern in test-manifest-schema-shape.py / test-runtime-schema-shape.py.
"""

import os
import re
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas/project-map.json.schema.json")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: schema file exists
if not os.path.isfile(SCHEMA_PATH):
    fail(f"schema file missing: {SCHEMA_PATH}")
    sys.exit(1)
ok("t1: project-map.json.schema.json exists")

# t2: schema is valid JSON
with open(SCHEMA_PATH) as f:
    try:
        schema = json.load(f)
    except json.JSONDecodeError as e:
        fail(f"not valid JSON: {e}")
        sys.exit(1)
ok("t2: project-map.json.schema.json parses as JSON")

# t3: $schema declared as draft-07
if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
    fail("t3: $schema is not draft-07")
else:
    ok("t3: $schema declares draft-07")

# t4: ownership-metadata triple
if not isinstance(schema.get("schema_version"), str) or not schema["schema_version"]:
    fail("t4: schema_version is missing or empty (spec-rules.md requires it)")
else:
    ok("t4a: schema_version is present")

if not isinstance(schema.get("owner"), str) or not schema["owner"]:
    fail("t4: owner is missing or empty (spec-rules.md requires it)")
else:
    ok("t4b: owner is present")

if not isinstance(schema.get("deprecation_criterion"), str) or not schema["deprecation_criterion"]:
    fail("t4: deprecation_criterion is missing or empty (spec-rules.md requires it)")
else:
    ok("t4c: deprecation_criterion is present")

# t5: outer type/required/additionalProperties
if schema.get("type") != "object":
    fail(f"t5: top-level type must be 'object', got {schema.get('type')!r}")
else:
    ok("t5a: top-level type is object")

required = set(schema.get("required", []))
if required != {"schema_version", "features"}:
    fail(f"t5: top-level required must be ['schema_version', 'features'], got {sorted(required)}")
else:
    ok("t5b: top-level required is [schema_version, features]")

if schema.get("additionalProperties") is not False:
    fail("t5: top-level additionalProperties must be false")
else:
    ok("t5c: top-level additionalProperties is false")

props = schema.get("properties", {})

# t6: schema_version property shape
sv_prop = props.get("schema_version", {})
if sv_prop.get("type") != "string":
    fail(f"t6: schema_version.type must be 'string', got {sv_prop.get('type')!r}")
else:
    ok("t6a: schema_version.type is string")

if sv_prop.get("pattern") != r"^\d+\.\d+\.\d+$":
    fail(f"t6: schema_version.pattern must be '^\\d+\\.\\d+\\.\\d+$', got {sv_prop.get('pattern')!r}")
else:
    ok("t6b: schema_version.pattern is semver")

# t7: features property shape
feat_prop = props.get("features", {})
if feat_prop.get("type") != "object":
    fail(f"t7: features.type must be 'object', got {feat_prop.get('type')!r}")
else:
    ok("t7a: features.type is object")

if feat_prop.get("additionalProperties") is not False:
    fail("t7: features.additionalProperties must be false")
else:
    ok("t7b: features.additionalProperties is false")

pattern_props = feat_prop.get("patternProperties", {})
if set(pattern_props.keys()) != {"^[a-z][a-z0-9-]*$"}:
    fail(f"t7: features.patternProperties must have exactly one key '^[a-z][a-z0-9-]*$', got {sorted(pattern_props.keys())}")
else:
    ok("t7c: features.patternProperties key is kebab-case regex")

value_schema = pattern_props.get("^[a-z][a-z0-9-]*$", {})
if value_schema.get("type") != "object":
    fail("t7: feature-value schema type must be 'object'")
else:
    ok("t7d: feature-value type is object")

vs_required = set(value_schema.get("required", []))
if vs_required != {"paths", "feature_dir"}:
    fail(f"t7: feature-value required must be ['paths', 'feature_dir'], got {sorted(vs_required)}")
else:
    ok("t7e: feature-value required is [paths, feature_dir]")

if value_schema.get("additionalProperties") is not False:
    fail("t7: feature-value additionalProperties must be false")
else:
    ok("t7f: feature-value additionalProperties is false")

vs_props = value_schema.get("properties", {})
paths_schema = vs_props.get("paths", {})
if paths_schema.get("type") != "array":
    fail("t7: paths.type must be 'array'")
else:
    ok("t7g: paths.type is array")

if paths_schema.get("minItems") != 1:
    fail(f"t7: paths.minItems must be 1, got {paths_schema.get('minItems')!r}")
else:
    ok("t7h: paths.minItems is 1")

if paths_schema.get("items", {}).get("type") != "string":
    fail("t7: paths.items.type must be 'string'")
else:
    ok("t7i: paths.items.type is string")

if vs_props.get("feature_dir", {}).get("type") != "string":
    fail("t7: feature_dir.type must be 'string'")
else:
    ok("t7j: feature_dir.type is string")


# Hand-rolled validator (subset of JSON Schema sufficient for project-map shape).
def validate(doc, sch):
    """Return list of error strings; empty list = valid."""
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
                # If no pattern matched and there are patternProperties defined
                # but no additionalProperties=false, key is implicitly permitted —
                # but for our use, patternProperties without a match + closed
                # shape must reject. The pattern_props loop already handled match.
                if pattern_props and not matched and additional is False:
                    # Already added above; avoid double-append guard.
                    pass
    elif t == "string":
        if not isinstance(doc, str):
            errs.append(f"expected string, got {type(doc).__name__}")
        else:
            pat = sch.get("pattern")
            if pat and not re.search(pat, doc):
                errs.append(f"string {doc!r} does not match pattern {pat!r}")
    elif t == "array":
        if not isinstance(doc, list):
            errs.append(f"expected array, got {type(doc).__name__}")
            return errs
        min_items = sch.get("minItems")
        if min_items is not None and len(doc) < min_items:
            errs.append(f"array has {len(doc)} items, minItems={min_items}")
        item_sch = sch.get("items")
        if item_sch:
            for i, item in enumerate(doc):
                errs.extend(f"[{i}]: {e}" for e in validate(item, item_sch))
    return errs


# t8: sample valid project-map.json validates
valid_doc = {
    "schema_version": "1.0.0",
    "features": {
        "auth": {
            "paths": ["../src/auth/**"],
            "feature_dir": "rabbit-project/features/auth",
        }
    },
}
errs = validate(valid_doc, schema)
if errs:
    fail(f"t8: valid sample doc rejected: {errs}")
else:
    ok("t8: valid sample project-map.json validates")

# t9: invalid samples fail validation
# t9a: missing required "features" key
invalid_a = {"schema_version": "1.0.0"}
errs_a = validate(invalid_a, schema)
if not errs_a:
    fail("t9a: missing-features doc was accepted")
else:
    ok("t9a: missing-features doc correctly rejected")

# t9b: key does not match ^[a-z][a-z0-9-]*$ (capital letter)
invalid_b = {
    "schema_version": "1.0.0",
    "features": {
        "Auth": {
            "paths": ["../src/auth/**"],
            "feature_dir": "rabbit-project/features/auth",
        }
    },
}
errs_b = validate(invalid_b, schema)
if not errs_b:
    fail("t9b: capital-letter key doc was accepted")
else:
    ok("t9b: capital-letter feature key correctly rejected")

# t9c: extra property on feature value
invalid_c = {
    "schema_version": "1.0.0",
    "features": {
        "auth": {
            "paths": ["../src/auth/**"],
            "feature_dir": "rabbit-project/features/auth",
            "extra": "x",
        }
    },
}
errs_c = validate(invalid_c, schema)
if not errs_c:
    fail("t9c: extra-property doc was accepted")
else:
    ok("t9c: extra-property on feature value correctly rejected")


if FAIL:
    print("test-project-map-schema-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-project-map-schema-shape: all checks passed.")
