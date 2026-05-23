# Meta-Contract Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the meta-contract foundation in the contract feature — three new JSON schemas (manifest, runtime, configuration), an updated feature.json schema that admits the three new sections, a hand-rolled validator function in `lib/checks.py`, a CLI shim, and tests wired into the contract test runner. This is Plan A of the larger architecture migration; lands additively (no other feature changes, no behavior change anywhere).

**Architecture:** Schemas live in `.claude/features/contract/schemas/`. Validator logic lives in `.claude/features/contract/lib/checks.py` (hand-rolled — Python stdlib only, no `jsonschema` dep). CLI shim follows the existing pattern: thin wrapper around the lib function returning `CheckResult`. Tests follow the existing pattern: one `test-*.py` per concern, wired into `test/run.py`.

**Tech Stack:** Python 3 (stdlib only), JSON Schema draft-07 (as documentation; validator is hand-rolled).

---

## Plan revisions (applied during execution)

Two universal rules surfaced from Task 1's code-quality review. They apply to every task below; the per-task code blocks pre-date the revisions and have NOT been re-edited inline.

**Revision R1 — Every task that adds a new test must wire it into `run.py` in the same commit.**

The contract test suite contains a self-enforcing meta-test (`test-run-invokes-all-active-tests.py`) that fails if any `test-*.py` file in the directory is not invoked by `run.py`. Deferring wiring to a single bulk Task 9 leaves the suite broken at every intermediate commit. So each task that creates a new test file must add a line of the shape

```python
run_test("<new-test-name>.py")
```

to `.claude/features/contract/test/run.py` BEFORE the commit step. This applies to Tasks 1, 2, 3, 4, 5, 6, 7, 8. Task 9 (originally "wire all tests") is collapsed to a final full-suite verification only.

**Revision R2 — Every new schema file must carry top-level `schema_version`, `owner`, `deprecation_criterion` keys.**

Every existing schema in `.claude/features/contract/schemas/` carries these per spec-rules.md. New schemas (Tasks 1, 2, 3) must do the same. Use:

```json
"schema_version": "1.0.0",
"owner": "rabbit-workflow team",
"deprecation_criterion": "<one-line condition for retirement>"
```

The corresponding shape test must assert all three fields are present and non-empty strings. Append these checks right after the `$schema` draft-07 check:

```python
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
```

Task 1 was completed with both revisions applied via a follow-up fix commit (`7f4659cb`). Tasks 2 onward must apply the revisions in their primary commit.

---

## Files to be created/modified

**Create:**
- `.claude/features/contract/schemas/manifest.schema.json`
- `.claude/features/contract/schemas/runtime.schema.json`
- `.claude/features/contract/schemas/configuration.schema.json`
- `.claude/features/contract/scripts/validate-meta-contract.py`
- `.claude/features/contract/test/test-manifest-schema-shape.py`
- `.claude/features/contract/test/test-runtime-schema-shape.py`
- `.claude/features/contract/test/test-configuration-schema-shape.py`
- `.claude/features/contract/test/test-feature-json-schema-admits-meta-contract.py`
- `.claude/features/contract/test/test-validate-meta-contract-manifest.py`
- `.claude/features/contract/test/test-validate-meta-contract-runtime.py`
- `.claude/features/contract/test/test-validate-meta-contract-configuration.py`
- `.claude/features/contract/test/test-validate-meta-contract-cli.py`

**Modify:**
- `.claude/features/contract/schemas/feature.json.schema.json` — add optional `manifest`, `runtime`, `configuration` properties
- `.claude/features/contract/lib/checks.py` — add `validate_meta_contract(feature_dir)` function
- `.claude/features/contract/test/run.py` — wire the 8 new tests

---

## Task 1: Create `manifest.schema.json`

**Files:**
- Create: `.claude/features/contract/schemas/manifest.schema.json`
- Test: `.claude/features/contract/test/test-manifest-schema-shape.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-manifest-schema-shape.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-manifest-schema-shape.py`  
Expected: FAIL with "schema file missing"

- [ ] **Step 3: Create `manifest.schema.json`**

Create `.claude/features/contract/schemas/manifest.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "manifest.schema.json",
  "title": "Feature MANIFEST",
  "description": "Declarative list of publish API calls a feature contributes at install time. The dispatcher reads this array and invokes each call in declaration order.",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["api", "args"],
    "additionalProperties": false,
    "properties": {
      "api": {
        "type": "string",
        "enum": [
          "publish_skill",
          "publish_command",
          "publish_agent",
          "publish_hook",
          "publish_settings",
          "publish_file",
          "publish_generated"
        ]
      },
      "args": {"type": "object"}
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-manifest-schema-shape.py`  
Expected: all PASS lines, exit 0

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/schemas/manifest.schema.json .claude/features/contract/test/test-manifest-schema-shape.py
git commit -m "feat(contract): add manifest.schema.json for meta-contract foundation

Closed enum for the 7 publish APIs; args object deferred to per-API
validation in Plan B (when API libraries are implemented)."
```

---

## Task 2: Create `runtime.schema.json`

**Files:**
- Create: `.claude/features/contract/schemas/runtime.schema.json`
- Test: `.claude/features/contract/test/test-runtime-schema-shape.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-runtime-schema-shape.py`:

```python
#!/usr/bin/env python3
"""test-runtime-schema-shape.py — validates runtime.schema.json shape:
top-level object keyed by Claude Code event names, each value an array of
{api, args} objects against the closed runtime API enum.
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

if FAIL:
    print("test-runtime-schema-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-schema-shape: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-runtime-schema-shape.py`  
Expected: FAIL with "schema file missing"

- [ ] **Step 3: Create `runtime.schema.json`**

Create `.claude/features/contract/schemas/runtime.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "runtime.schema.json",
  "title": "Feature RUNTIME",
  "description": "Per-event lists of runtime API calls. The dispatcher hook for each Claude Code event invokes the calls in declaration order and aggregates typed returns.",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "Stop": {"$ref": "#/definitions/call_list"},
    "SessionStart": {"$ref": "#/definitions/call_list"},
    "UserPromptSubmit": {"$ref": "#/definitions/call_list"},
    "PreToolUse": {"$ref": "#/definitions/call_list"}
  },
  "definitions": {
    "call_list": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["api", "args"],
        "additionalProperties": false,
        "properties": {
          "api": {
            "type": "string",
            "enum": [
              "check_drift_regenerate",
              "check_manifest_drift",
              "check_marker_alert",
              "check_marker_consume_alert",
              "check_counter_threshold_refresh",
              "welcome_with_policy",
              "iterate_configurables_alerts",
              "iterate_configurables_banner"
            ]
          },
          "args": {"type": "object"}
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-runtime-schema-shape.py`  
Expected: all PASS, exit 0

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/schemas/runtime.schema.json .claude/features/contract/test/test-runtime-schema-shape.py
git commit -m "feat(contract): add runtime.schema.json for meta-contract foundation

Closed event set (Stop, SessionStart, UserPromptSubmit, PreToolUse) and
closed runtime API enum. Per-API args validation deferred to Plan B."
```

---

## Task 3: Create `configuration.schema.json`

**Files:**
- Create: `.claude/features/contract/schemas/configuration.schema.json`
- Test: `.claude/features/contract/test/test-configuration-schema-shape.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-configuration-schema-shape.py`:

```python
#!/usr/bin/env python3
"""test-configuration-schema-shape.py — validates configuration.schema.json
shape: top-level array of configurable declarations; each requires id +
subcommand; mutation API enum is closed; storage type enum is closed;
each item must declare exactly one of `values` or `actions` (oneOf).
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

if schema.get("type") != "array":
    fail(f"top-level type must be 'array', got {schema.get('type')!r}")
else:
    ok("top-level type is array")

items = schema.get("items", {})
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

api_call = schema.get("definitions", {}).get("api_call", {})
api_enum = set(api_call.get("properties", {}).get("api", {}).get("enum", []))
if api_enum != EXPECTED_MUTATION_APIS:
    missing = EXPECTED_MUTATION_APIS - api_enum
    extra = api_enum - EXPECTED_MUTATION_APIS
    fail(f"mutation api enum mismatch — missing: {sorted(missing)}, extra: {sorted(extra)}")
else:
    ok("mutation api enum is the closed mutation API set")

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

if FAIL:
    print("test-configuration-schema-shape: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-configuration-schema-shape: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-configuration-schema-shape.py`  
Expected: FAIL

- [ ] **Step 3: Create `configuration.schema.json`**

Create `.claude/features/contract/schemas/configuration.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "configuration.schema.json",
  "title": "Feature CONFIGURATION",
  "description": "Declarations of user-mutable configurables. Each declares an id, subcommand, storage location, mutation API per value or action, default state, and optional active-override alert. rabbit-config reads these declarations at runtime to dispatch /rabbit-config calls and emit Stop alerts.",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["id", "subcommand"],
    "additionalProperties": false,
    "properties": {
      "id": {"type": "string", "minLength": 1},
      "subcommand": {"type": "string", "minLength": 1},
      "storage": {
        "type": "object",
        "required": ["type"],
        "additionalProperties": true,
        "properties": {
          "type": {
            "type": "string",
            "enum": ["marker-file", "json-key", "json-array", "json-array-templated"]
          }
        }
      },
      "values": {
        "type": "object",
        "additionalProperties": {"$ref": "#/definitions/api_call"}
      },
      "actions": {
        "type": "object",
        "additionalProperties": {"$ref": "#/definitions/api_call"}
      },
      "default": {"type": "string"},
      "alert-on": {"type": "string"},
      "alert-message": {
        "type": "object",
        "required": ["text", "icon", "color"],
        "additionalProperties": false,
        "properties": {
          "text": {"type": "string"},
          "icon": {"type": "string"},
          "color": {"type": "string", "enum": ["red", "green", "yellow"]}
        }
      },
      "validation": {
        "type": "object",
        "additionalProperties": true
      }
    },
    "oneOf": [
      {"required": ["values"]},
      {"required": ["actions"]}
    ]
  },
  "definitions": {
    "api_call": {
      "type": "object",
      "required": ["api", "args"],
      "additionalProperties": false,
      "properties": {
        "api": {
          "type": "string",
          "enum": [
            "write_marker",
            "delete_marker",
            "set_json_key",
            "delete_json_key",
            "append_json_array",
            "remove_json_array_value",
            "run_feature_script"
          ]
        },
        "args": {"type": "object"}
      }
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-configuration-schema-shape.py`  
Expected: all PASS, exit 0

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/schemas/configuration.schema.json .claude/features/contract/test/test-configuration-schema-shape.py
git commit -m "feat(contract): add configuration.schema.json for meta-contract foundation

Closed storage-type vocabulary (4 types), closed mutation API enum (7),
oneOf enforces exactly-one of values/actions, closed color enum for alerts."
```

---

## Task 4: Update `feature.json.schema.json` to admit meta-contract sections

**Files:**
- Modify: `.claude/features/contract/schemas/feature.json.schema.json` (add 3 optional properties)
- Test: `.claude/features/contract/test/test-feature-json-schema-admits-meta-contract.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-feature-json-schema-admits-meta-contract.py`:

```python
#!/usr/bin/env python3
"""test-feature-json-schema-admits-meta-contract.py — verifies that
feature.json.schema.json declares optional properties for manifest, runtime,
and configuration referencing the three new schemas.
"""

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas/feature.json.schema.json")

EXPECTED_REFS = {
    "manifest": "manifest.schema.json",
    "runtime": "runtime.schema.json",
    "configuration": "configuration.schema.json",
}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


with open(SCHEMA_PATH) as f:
    schema = json.load(f)

props = schema.get("properties", {})
for key, expected_ref in EXPECTED_REFS.items():
    if key not in props:
        fail(f"feature.json.schema.json missing property '{key}'")
        continue
    ref = props[key].get("$ref")
    if ref != expected_ref:
        fail(f"property '{key}' must $ref '{expected_ref}', got {ref!r}")
    else:
        ok(f"property '{key}' references '{expected_ref}'")

# None of the three must be in required (they're optional per design)
required = set(schema.get("required", []))
for key in EXPECTED_REFS:
    if key in required:
        fail(f"property '{key}' must be OPTIONAL (not in required[]), but is in required")
    else:
        ok(f"property '{key}' is optional (not in required[])")

if FAIL:
    print("test-feature-json-schema-admits-meta-contract: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-feature-json-schema-admits-meta-contract: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-feature-json-schema-admits-meta-contract.py`  
Expected: FAIL on all three "property X missing"

- [ ] **Step 3: Update `feature.json.schema.json`**

Open `.claude/features/contract/schemas/feature.json.schema.json` and add three properties inside the `properties` object (after `deprecation_criterion`, before the closing brace of `properties`):

```json
    "manifest": {
      "$ref": "manifest.schema.json",
      "description": "Optional MANIFEST — declarative list of publish API calls executed at install time."
    },
    "runtime": {
      "$ref": "runtime.schema.json",
      "description": "Optional RUNTIME — per-event lists of runtime API calls invoked by the dispatcher."
    },
    "configuration": {
      "$ref": "configuration.schema.json",
      "description": "Optional CONFIGURATION — declarations of user-mutable configurables."
    }
```

These are NOT added to the top-level `required` array — meta-contract sections are optional (per design; existing features can omit them during incremental migration).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-feature-json-schema-admits-meta-contract.py`  
Expected: all PASS, exit 0

- [ ] **Step 5: Sanity-check no existing tests broke**

Run: `python3 .claude/features/contract/test/run.py`  
Expected: ALL existing tests still pass (the new feature.json schema additions are purely additive; existing feature.json files validate unchanged because the three new properties are optional).

If any existing test fails: revert the feature.json.schema.json change, investigate, fix the regression before continuing.

- [ ] **Step 6: Commit**

```bash
git add .claude/features/contract/schemas/feature.json.schema.json .claude/features/contract/test/test-feature-json-schema-admits-meta-contract.py
git commit -m "feat(contract): admit meta-contract sections in feature.json schema

Optional manifest/runtime/configuration properties referencing the new
schemas. Additive — existing feature.json files validate unchanged."
```

---

## Task 5: Add `validate_meta_contract` to `lib/checks.py` — manifest section

**Files:**
- Modify: `.claude/features/contract/lib/checks.py` (append new function + helper)
- Test: `.claude/features/contract/test/test-validate-meta-contract-manifest.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-validate-meta-contract-manifest.py`:

```python
#!/usr/bin/env python3
"""test-validate-meta-contract-manifest.py — exercises the manifest-section
arm of validate_meta_contract. Uses inline fixture feature.json files in a
temp dir so no live features are touched.
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from lib.checks import validate_meta_contract  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_feature(tmpdir, data):
    path = os.path.join(tmpdir, "feature.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return tmpdir


with tempfile.TemporaryDirectory() as td:
    # t1: feature.json with no manifest section → pass (optional)
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x"})
    r = validate_meta_contract(td)
    if r.passed:
        ok("t1: absent manifest section is accepted")
    else:
        fail(f"t1: absent manifest rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t2: valid empty manifest → pass
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x", "manifest": []})
    r = validate_meta_contract(td)
    if r.passed:
        ok("t2: empty manifest array is accepted")
    else:
        fail(f"t2: empty manifest rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t3: valid populated manifest → pass
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": [
                           {"api": "publish_skill", "args": {"source": "skills/x/SKILL.md"}},
                           {"api": "publish_hook", "args": {"event": "Stop", "source": "hooks/x.py"}}
                       ]})
    r = validate_meta_contract(td)
    if r.passed:
        ok("t3: populated valid manifest is accepted")
    else:
        fail(f"t3: valid manifest rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t4: manifest is not an array → fail with descriptive error
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": {"api": "x"}})
    r = validate_meta_contract(td)
    if not r.passed and any("must be an array" in m for m in r.messages):
        ok("t4: non-array manifest is rejected with descriptive message")
    else:
        fail(f"t4: non-array manifest acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t5: manifest item missing 'api' → fail
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": [{"args": {}}]})
    r = validate_meta_contract(td)
    if not r.passed and any("missing required 'api'" in m for m in r.messages):
        ok("t5: manifest item missing 'api' is rejected")
    else:
        fail(f"t5: missing-api acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t6: manifest item with unknown api → fail
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": [{"api": "publish_bogus", "args": {}}]})
    r = validate_meta_contract(td)
    if not r.passed and any("unknown publish api" in m for m in r.messages):
        ok("t6: unknown api is rejected")
    else:
        fail(f"t6: unknown-api acceptance bug: passed={r.passed}, messages={r.messages}")

if FAIL:
    print("test-validate-meta-contract-manifest: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-manifest: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-validate-meta-contract-manifest.py`  
Expected: FAIL with ImportError or AttributeError (validate_meta_contract does not yet exist)

- [ ] **Step 3: Add `validate_meta_contract` to `lib/checks.py`**

Open `.claude/features/contract/lib/checks.py`. Add at the END of the file (after existing functions):

```python
# ---------------------------------------------------------------------------
# Meta-contract validation (Plan A — manifest section only; runtime and
# configuration arms added in Tasks 6 and 7).
# ---------------------------------------------------------------------------

_PUBLISH_API_ENUM = frozenset({
    "publish_skill",
    "publish_command",
    "publish_agent",
    "publish_hook",
    "publish_settings",
    "publish_file",
    "publish_generated",
})


def _validate_manifest(manifest):
    """Validate a manifest declaration. Returns list of error message strings."""
    errors = []
    if not isinstance(manifest, list):
        errors.append(f"manifest must be an array, got {type(manifest).__name__}")
        return errors
    for i, item in enumerate(manifest):
        if not isinstance(item, dict):
            errors.append(f"manifest[{i}] must be an object, got {type(item).__name__}")
            continue
        if "api" not in item:
            errors.append(f"manifest[{i}] missing required 'api' field")
            continue
        if "args" not in item:
            errors.append(f"manifest[{i}] missing required 'args' field")
            continue
        if item["api"] not in _PUBLISH_API_ENUM:
            errors.append(f"manifest[{i}]: unknown publish api {item['api']!r} (valid: {sorted(_PUBLISH_API_ENUM)})")
        if not isinstance(item["args"], dict):
            errors.append(f"manifest[{i}].args must be an object, got {type(item['args']).__name__}")
        extra_keys = set(item.keys()) - {"api", "args"}
        if extra_keys:
            errors.append(f"manifest[{i}]: unexpected keys {sorted(extra_keys)} (only api and args allowed)")
    return errors


def validate_meta_contract(feature_dir):
    """Validate a feature's meta-contract sections (manifest/runtime/configuration).

    Each section is optional. Returns a CheckResult; passed=True iff every
    declared section validates against its schema rules.
    """
    import os, json
    feature_json_path = os.path.join(feature_dir, "feature.json")
    if not os.path.isfile(feature_json_path):
        return CheckResult(passed=False, messages=[f"feature.json missing at {feature_json_path}"])
    try:
        with open(feature_json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return CheckResult(passed=False, messages=[f"feature.json invalid JSON: {e}"])

    errors = []
    if "manifest" in data:
        errors.extend(_validate_manifest(data["manifest"]))
    # runtime and configuration arms added in Tasks 6 and 7.

    if errors:
        return CheckResult(passed=False, messages=errors)
    return CheckResult(passed=True, messages=["meta-contract sections valid (or absent)"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-validate-meta-contract-manifest.py`  
Expected: all PASS, exit 0

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/lib/checks.py .claude/features/contract/test/test-validate-meta-contract-manifest.py
git commit -m "feat(contract): validate_meta_contract — manifest arm

Hand-rolled validator (stdlib only — no jsonschema dep). Tests cover
absent/empty/populated valid manifests and three error classes:
non-array, missing required key, unknown api enum value."
```

---

## Task 6: Add runtime-section validation to `validate_meta_contract`

**Files:**
- Modify: `.claude/features/contract/lib/checks.py` (extend `validate_meta_contract`)
- Test: `.claude/features/contract/test/test-validate-meta-contract-runtime.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-validate-meta-contract-runtime.py`:

```python
#!/usr/bin/env python3
"""test-validate-meta-contract-runtime.py — exercises the runtime-section
arm of validate_meta_contract.
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from lib.checks import validate_meta_contract  # noqa: E402

BASE = {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x"}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write(tmpdir, runtime):
    data = dict(BASE)
    data["runtime"] = runtime
    with open(os.path.join(tmpdir, "feature.json"), "w") as f:
        json.dump(data, f)
    return tmpdir


with tempfile.TemporaryDirectory() as td:
    # t1: empty runtime object → pass
    r = validate_meta_contract(write(td, {}))
    if r.passed:
        ok("t1: empty runtime object is accepted")
    else:
        fail(f"t1: empty runtime rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t2: valid runtime with one Stop call → pass
    r = validate_meta_contract(write(td, {
        "Stop": [{"api": "check_marker_alert", "args": {"path": ".x", "alert": {"text": "x", "icon": "x", "color": "red"}}}]
    }))
    if r.passed:
        ok("t2: valid Stop runtime is accepted")
    else:
        fail(f"t2: valid runtime rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t3: runtime not an object → fail
    r = validate_meta_contract(write(td, ["bad"]))
    if not r.passed and any("must be an object" in m for m in r.messages):
        ok("t3: non-object runtime is rejected")
    else:
        fail(f"t3: non-object runtime acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t4: unknown event key → fail
    r = validate_meta_contract(write(td, {"Foo": []}))
    if not r.passed and any("unknown event" in m for m in r.messages):
        ok("t4: unknown event key is rejected")
    else:
        fail(f"t4: unknown event acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t5: event value not an array → fail
    r = validate_meta_contract(write(td, {"Stop": {"api": "x"}}))
    if not r.passed and any("must be an array" in m for m in r.messages):
        ok("t5: non-array event value is rejected")
    else:
        fail(f"t5: non-array event acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t6: unknown runtime api → fail
    r = validate_meta_contract(write(td, {"Stop": [{"api": "check_bogus", "args": {}}]}))
    if not r.passed and any("unknown runtime api" in m for m in r.messages):
        ok("t6: unknown runtime api is rejected")
    else:
        fail(f"t6: unknown runtime api acceptance bug: passed={r.passed}, messages={r.messages}")

if FAIL:
    print("test-validate-meta-contract-runtime: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-runtime: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-validate-meta-contract-runtime.py`  
Expected: at least t2 fails (validate_meta_contract has no runtime arm yet, so runtime data is silently accepted but for wrong reasons; OR tests fail because runtime is unvalidated)

- [ ] **Step 3: Extend `validate_meta_contract` with runtime arm**

In `.claude/features/contract/lib/checks.py`, add the following BEFORE the `validate_meta_contract` function definition:

```python
_RUNTIME_EVENT_ENUM = frozenset({"Stop", "SessionStart", "UserPromptSubmit", "PreToolUse"})

_RUNTIME_API_ENUM = frozenset({
    "check_drift_regenerate",
    "check_manifest_drift",
    "check_marker_alert",
    "check_marker_consume_alert",
    "check_counter_threshold_refresh",
    "welcome_with_policy",
    "iterate_configurables_alerts",
    "iterate_configurables_banner",
})


def _validate_runtime(runtime):
    """Validate a runtime declaration. Returns list of error message strings."""
    errors = []
    if not isinstance(runtime, dict):
        errors.append(f"runtime must be an object, got {type(runtime).__name__}")
        return errors
    for event, calls in runtime.items():
        if event not in _RUNTIME_EVENT_ENUM:
            errors.append(f"runtime: unknown event {event!r} (valid: {sorted(_RUNTIME_EVENT_ENUM)})")
            continue
        if not isinstance(calls, list):
            errors.append(f"runtime[{event!r}] must be an array, got {type(calls).__name__}")
            continue
        for i, item in enumerate(calls):
            if not isinstance(item, dict):
                errors.append(f"runtime[{event!r}][{i}] must be an object")
                continue
            if "api" not in item or "args" not in item:
                errors.append(f"runtime[{event!r}][{i}] missing required 'api' or 'args'")
                continue
            if item["api"] not in _RUNTIME_API_ENUM:
                errors.append(f"runtime[{event!r}][{i}]: unknown runtime api {item['api']!r}")
            if not isinstance(item["args"], dict):
                errors.append(f"runtime[{event!r}][{i}].args must be an object")
            extra_keys = set(item.keys()) - {"api", "args"}
            if extra_keys:
                errors.append(f"runtime[{event!r}][{i}]: unexpected keys {sorted(extra_keys)}")
    return errors
```

Then update `validate_meta_contract` to wire the runtime arm. Change this section:

```python
    errors = []
    if "manifest" in data:
        errors.extend(_validate_manifest(data["manifest"]))
    # runtime and configuration arms added in Tasks 6 and 7.
```

…to:

```python
    errors = []
    if "manifest" in data:
        errors.extend(_validate_manifest(data["manifest"]))
    if "runtime" in data:
        errors.extend(_validate_runtime(data["runtime"]))
    # configuration arm added in Task 7.
```

- [ ] **Step 4: Run BOTH manifest and runtime tests**

Run: `python3 .claude/features/contract/test/test-validate-meta-contract-manifest.py && python3 .claude/features/contract/test/test-validate-meta-contract-runtime.py`  
Expected: both all-PASS, exit 0

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/lib/checks.py .claude/features/contract/test/test-validate-meta-contract-runtime.py
git commit -m "feat(contract): validate_meta_contract — runtime arm

Closed event set + closed runtime API enum; six failure modes covered
in tests (non-object, unknown event, non-array event value, missing
required keys, unknown api, extra keys)."
```

---

## Task 7: Add configuration-section validation to `validate_meta_contract`

**Files:**
- Modify: `.claude/features/contract/lib/checks.py` (extend `validate_meta_contract`)
- Test: `.claude/features/contract/test/test-validate-meta-contract-configuration.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-validate-meta-contract-configuration.py`:

```python
#!/usr/bin/env python3
"""test-validate-meta-contract-configuration.py — exercises the
configuration-section arm of validate_meta_contract.
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from lib.checks import validate_meta_contract  # noqa: E402

BASE = {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x"}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write(tmpdir, cfg):
    data = dict(BASE)
    data["configuration"] = cfg
    with open(os.path.join(tmpdir, "feature.json"), "w") as f:
        json.dump(data, f)
    return tmpdir


VALID_VALUES_ENTRY = {
    "id": "x", "subcommand": "x",
    "storage": {"type": "marker-file", "path": ".x"},
    "values": {
        "true":  {"api": "delete_marker", "args": {"path": ".x"}},
        "false": {"api": "write_marker",  "args": {"path": ".x", "content": "y"}}
    },
    "default": "true"
}

VALID_ACTIONS_ENTRY = {
    "id": "x", "subcommand": "x",
    "actions": {
        "lock":   {"api": "run_feature_script", "args": {"script": "scripts/x.py"}},
        "unlock": {"api": "run_feature_script", "args": {"script": "scripts/x.py"}}
    }
}


with tempfile.TemporaryDirectory() as td:
    # t1: empty configuration array → pass
    r = validate_meta_contract(write(td, []))
    if r.passed:
        ok("t1: empty configuration array is accepted")
    else:
        fail(f"t1: empty configuration rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t2: valid values-style entry → pass
    r = validate_meta_contract(write(td, [VALID_VALUES_ENTRY]))
    if r.passed:
        ok("t2: valid values-style entry is accepted")
    else:
        fail(f"t2: valid values rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t3: valid actions-style entry → pass
    r = validate_meta_contract(write(td, [VALID_ACTIONS_ENTRY]))
    if r.passed:
        ok("t3: valid actions-style entry is accepted")
    else:
        fail(f"t3: valid actions rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t4: configuration not an array → fail
    r = validate_meta_contract(write(td, {"id": "x"}))
    if not r.passed and any("must be an array" in m for m in r.messages):
        ok("t4: non-array configuration is rejected")
    else:
        fail(f"t4: non-array acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t5: entry missing id → fail
    bad = dict(VALID_VALUES_ENTRY); del bad["id"]
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("missing required 'id'" in m for m in r.messages):
        ok("t5: entry missing 'id' is rejected")
    else:
        fail(f"t5: missing-id acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t6: entry with both values AND actions → fail (oneOf)
    bad = dict(VALID_VALUES_ENTRY)
    bad["actions"] = VALID_ACTIONS_ENTRY["actions"]
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("exactly one of 'values' or 'actions'" in m for m in r.messages):
        ok("t6: both values and actions is rejected (oneOf)")
    else:
        fail(f"t6: both-values-and-actions acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t7: entry with neither values nor actions → fail (oneOf)
    bad = {"id": "x", "subcommand": "x"}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("exactly one of 'values' or 'actions'" in m for m in r.messages):
        ok("t7: neither values nor actions is rejected (oneOf)")
    else:
        fail(f"t7: neither-values-nor-actions acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t8: unknown mutation api → fail
    bad = dict(VALID_VALUES_ENTRY)
    bad["values"] = {"true": {"api": "mutate_bogus", "args": {}}}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("unknown mutation api" in m for m in r.messages):
        ok("t8: unknown mutation api is rejected")
    else:
        fail(f"t8: unknown-mutation-api acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t9: unknown storage type → fail
    bad = dict(VALID_VALUES_ENTRY)
    bad["storage"] = {"type": "magic"}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("unknown storage type" in m for m in r.messages):
        ok("t9: unknown storage type is rejected")
    else:
        fail(f"t9: unknown-storage-type acceptance bug: passed={r.passed}, messages={r.messages}")

if FAIL:
    print("test-validate-meta-contract-configuration: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-configuration: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-validate-meta-contract-configuration.py`  
Expected: FAIL (no configuration arm yet)

- [ ] **Step 3: Extend `validate_meta_contract` with configuration arm**

In `.claude/features/contract/lib/checks.py`, add BEFORE `validate_meta_contract`:

```python
_STORAGE_TYPE_ENUM = frozenset({"marker-file", "json-key", "json-array", "json-array-templated"})

_MUTATION_API_ENUM = frozenset({
    "write_marker",
    "delete_marker",
    "set_json_key",
    "delete_json_key",
    "append_json_array",
    "remove_json_array_value",
    "run_feature_script",
})

_COLOR_ENUM = frozenset({"red", "green", "yellow"})


def _validate_api_call(item, ctx):
    """Validate a single {api, args} mutation call. Returns list of errors."""
    errors = []
    if not isinstance(item, dict):
        errors.append(f"{ctx}: must be an object, got {type(item).__name__}")
        return errors
    if "api" not in item or "args" not in item:
        errors.append(f"{ctx}: missing required 'api' or 'args'")
        return errors
    if item["api"] not in _MUTATION_API_ENUM:
        errors.append(f"{ctx}: unknown mutation api {item['api']!r}")
    if not isinstance(item["args"], dict):
        errors.append(f"{ctx}.args must be an object")
    extra = set(item.keys()) - {"api", "args"}
    if extra:
        errors.append(f"{ctx}: unexpected keys {sorted(extra)}")
    return errors


def _validate_configuration(configuration):
    """Validate a configuration declaration. Returns list of error message strings."""
    errors = []
    if not isinstance(configuration, list):
        errors.append(f"configuration must be an array, got {type(configuration).__name__}")
        return errors
    for i, entry in enumerate(configuration):
        ctx = f"configuration[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{ctx} must be an object")
            continue
        if "id" not in entry:
            errors.append(f"{ctx} missing required 'id'")
            continue
        if "subcommand" not in entry:
            errors.append(f"{ctx} missing required 'subcommand'")
            continue
        has_values = "values" in entry
        has_actions = "actions" in entry
        if has_values == has_actions:
            errors.append(f"{ctx} must declare exactly one of 'values' or 'actions' (oneOf)")
        if has_values:
            if not isinstance(entry["values"], dict):
                errors.append(f"{ctx}.values must be an object")
            else:
                for k, call in entry["values"].items():
                    errors.extend(_validate_api_call(call, f"{ctx}.values[{k!r}]"))
        if has_actions:
            if not isinstance(entry["actions"], dict):
                errors.append(f"{ctx}.actions must be an object")
            else:
                for k, call in entry["actions"].items():
                    errors.extend(_validate_api_call(call, f"{ctx}.actions[{k!r}]"))
        if "storage" in entry:
            storage = entry["storage"]
            if not isinstance(storage, dict):
                errors.append(f"{ctx}.storage must be an object")
            elif storage.get("type") not in _STORAGE_TYPE_ENUM:
                errors.append(f"{ctx}.storage: unknown storage type {storage.get('type')!r}")
        if "alert-message" in entry:
            am = entry["alert-message"]
            if not isinstance(am, dict):
                errors.append(f"{ctx}.alert-message must be an object")
            else:
                for k in ("text", "icon", "color"):
                    if k not in am:
                        errors.append(f"{ctx}.alert-message missing required '{k}'")
                if am.get("color") not in _COLOR_ENUM:
                    errors.append(f"{ctx}.alert-message.color must be one of {sorted(_COLOR_ENUM)}, got {am.get('color')!r}")
    return errors
```

Then update `validate_meta_contract` to wire the configuration arm. Change:

```python
    if "runtime" in data:
        errors.extend(_validate_runtime(data["runtime"]))
    # configuration arm added in Task 7.
```

…to:

```python
    if "runtime" in data:
        errors.extend(_validate_runtime(data["runtime"]))
    if "configuration" in data:
        errors.extend(_validate_configuration(data["configuration"]))
```

- [ ] **Step 4: Run ALL three validator tests**

Run:
```bash
python3 .claude/features/contract/test/test-validate-meta-contract-manifest.py && \
python3 .claude/features/contract/test/test-validate-meta-contract-runtime.py && \
python3 .claude/features/contract/test/test-validate-meta-contract-configuration.py
```
Expected: all all-PASS, exit 0

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/lib/checks.py .claude/features/contract/test/test-validate-meta-contract-configuration.py
git commit -m "feat(contract): validate_meta_contract — configuration arm

Closed storage-type vocabulary + closed mutation API enum + closed
color enum + oneOf(values, actions). validate_meta_contract is now
complete; nine failure modes covered in the configuration test."
```

---

## Task 8: Create CLI shim `validate-meta-contract.py`

**Files:**
- Create: `.claude/features/contract/scripts/validate-meta-contract.py`
- Test: `.claude/features/contract/test/test-validate-meta-contract-cli.py`

- [ ] **Step 1: Write the failing test**

Create `.claude/features/contract/test/test-validate-meta-contract-cli.py`:

```python
#!/usr/bin/env python3
"""test-validate-meta-contract-cli.py — exercises the CLI shim:
- exit 0 on valid feature dir
- exit 1 on invalid feature dir (with messages to stderr)
- exit 2 on invocation error (missing argv, non-directory path)
- has module-level docstring (per Inv 16)
"""

import os
import sys
import json
import subprocess
import tempfile

SCRIPT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "validate-meta-contract.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: script exists and is executable
if not os.path.isfile(SCRIPT):
    fail(f"script missing: {SCRIPT}")
    sys.exit(1)
ok("script exists")
if not os.access(SCRIPT, os.X_OK):
    fail("script not executable (chmod +x)")
else:
    ok("script is executable")

# t2: has module docstring (per Inv 16)
with open(SCRIPT) as f:
    src = f.read()
first_lines = "\n".join(src.split("\n")[:5])
if '"""' not in first_lines:
    fail("script missing module-level docstring near top of file (per Inv 16)")
else:
    ok("script has module-level docstring")

# t3: missing argv → exit 2
res = subprocess.run(["python3", SCRIPT], capture_output=True, text=True)
if res.returncode != 2:
    fail(f"missing-argv expected exit 2, got {res.returncode}; stderr={res.stderr!r}")
else:
    ok("missing argv → exit 2")

# t4: non-directory path → exit 2
res = subprocess.run(["python3", SCRIPT, "/nonexistent/path"], capture_output=True, text=True)
if res.returncode != 2:
    fail(f"non-directory expected exit 2, got {res.returncode}")
else:
    ok("non-directory → exit 2")

# t5: valid feature dir → exit 0
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "feature.json"), "w") as f:
        json.dump({"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                   "manifest": [{"api": "publish_skill", "args": {"source": "x"}}]}, f)
    res = subprocess.run(["python3", SCRIPT, td], capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"valid feature expected exit 0, got {res.returncode}; stderr={res.stderr!r}")
    else:
        ok("valid feature dir → exit 0")

# t6: invalid feature dir → exit 1 with stderr message
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, "feature.json"), "w") as f:
        json.dump({"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                   "manifest": [{"api": "publish_bogus", "args": {}}]}, f)
    res = subprocess.run(["python3", SCRIPT, td], capture_output=True, text=True)
    if res.returncode != 1:
        fail(f"invalid feature expected exit 1, got {res.returncode}")
    elif "unknown publish api" not in res.stderr:
        fail(f"invalid feature did not surface error to stderr: {res.stderr!r}")
    else:
        ok("invalid feature dir → exit 1 with error on stderr")

if FAIL:
    print("test-validate-meta-contract-cli: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-cli: all checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 .claude/features/contract/test/test-validate-meta-contract-cli.py`  
Expected: FAIL with "script missing"

- [ ] **Step 3: Create the CLI shim**

Create `.claude/features/contract/scripts/validate-meta-contract.py`:

```python
#!/usr/bin/env python3
"""validate-meta-contract.py — thin CLI shim around
contract.lib.checks.validate_meta_contract.

Usage: validate-meta-contract.py <feature-dir>
Exit:  0 pass; 1 validation error(s); 2 invocation error.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when meta-contract validation is provided natively by the rabbit CLI.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
from lib.checks import validate_meta_contract  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1]:
        print("usage: validate-meta-contract.py <feature-dir>", file=sys.stderr)
        return 2
    feature_dir = sys.argv[1]
    if not os.path.isdir(feature_dir):
        print(f"ERROR: not a directory: {feature_dir}", file=sys.stderr)
        return 2
    result = validate_meta_contract(feature_dir)
    stream = sys.stdout if result.passed else sys.stderr
    for line in result.messages:
        print(line, file=stream)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

Make it executable:

```bash
chmod +x .claude/features/contract/scripts/validate-meta-contract.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 .claude/features/contract/test/test-validate-meta-contract-cli.py`  
Expected: all PASS, exit 0

- [ ] **Step 5: Commit**

```bash
git add .claude/features/contract/scripts/validate-meta-contract.py .claude/features/contract/test/test-validate-meta-contract-cli.py
git commit -m "feat(contract): add validate-meta-contract.py CLI shim

Mirrors validate-feature.py pattern: thin wrapper around the lib
function returning CheckResult. Exit codes: 0 pass, 1 validation
error, 2 invocation error."
```

---

## Task 9: Wire all 8 new tests into `test/run.py` and verify

**Files:**
- Modify: `.claude/features/contract/test/run.py` (append 8 `run_test(...)` lines)

- [ ] **Step 1: Append new test invocations to `run.py`**

Open `.claude/features/contract/test/run.py`. After the last `run_test(...)` line (currently `run_test("test-check-invariant-monotonic-order.py")`), append:

```python
run_test("test-manifest-schema-shape.py")
run_test("test-runtime-schema-shape.py")
run_test("test-configuration-schema-shape.py")
run_test("test-feature-json-schema-admits-meta-contract.py")
run_test("test-validate-meta-contract-manifest.py")
run_test("test-validate-meta-contract-runtime.py")
run_test("test-validate-meta-contract-configuration.py")
run_test("test-validate-meta-contract-cli.py")
```

- [ ] **Step 2: Run the full contract test suite**

Run: `python3 .claude/features/contract/test/run.py`  
Expected: every test PASS; final exit 0.

If any existing test fails: the schema-additive change should not have broken anything, so investigate the failure. Most likely culprits:
- `test-run-invokes-all-active-tests.py` — verifies run.py invokes every test in the directory; the new lines should satisfy it
- `test-no-dead-contract-scripts.py` — verifies every script has a caller; `validate-meta-contract.py` is called only by tests today, so check whether that counts as a "production caller" per Inv 34. If it doesn't, add the script's name to whatever allowlist exists for not-yet-wired scripts, OR document the test-only justification in the test failure resolution.

- [ ] **Step 3: Commit**

```bash
git add .claude/features/contract/test/run.py
git commit -m "test(contract): wire 8 meta-contract foundation tests into run.py

Completes Plan A meta-contract foundation: schemas, validator, CLI shim
all exercised by the contract test runner."
```

---

## Task 10: Update contract spec to document the meta-contract foundation

**Files:**
- Modify: `.claude/features/contract/docs/spec/spec.md` (add 4 new invariants)
- Modify: `.claude/features/contract/feature.json` (bump version per Inv 58 if applicable — for contract feature this is the contract spec's own version field in frontmatter)

- [ ] **Step 1: Add four new invariants to contract spec**

Open `.claude/features/contract/docs/spec/spec.md`. After Invariant 39 (the last existing invariant), append:

```markdown

40. **MANIFEST schema (Plan A foundation).** `.claude/features/contract/schemas/manifest.schema.json` MUST exist, be valid JSON, declare `$schema` as draft-07, describe `type: "array"` with `items` requiring exactly `{api, args}` (additionalProperties false), and enumerate the closed publish API set: `publish_skill, publish_command, publish_agent, publish_hook, publish_settings, publish_file, publish_generated`. The shape is validated by `test/test-manifest-schema-shape.py`. Per-API args validation is deferred to Plan B (when the publish API library is implemented).

41. **RUNTIME schema (Plan A foundation).** `.claude/features/contract/schemas/runtime.schema.json` MUST exist, be valid JSON, draft-07, declare `type: "object"` with `additionalProperties: false`, and enumerate the closed Claude Code event set as `properties`: `Stop, SessionStart, UserPromptSubmit, PreToolUse` — each `$ref`'d to a `call_list` definition that enumerates the closed runtime API set (`check_drift_regenerate, check_manifest_drift, check_marker_alert, check_marker_consume_alert, check_counter_threshold_refresh, welcome_with_policy, iterate_configurables_alerts, iterate_configurables_banner`). The shape is validated by `test/test-runtime-schema-shape.py`.

42. **CONFIGURATION schema (Plan A foundation).** `.claude/features/contract/schemas/configuration.schema.json` MUST exist, be valid JSON, draft-07, declare `type: "array"` with `items` requiring `id` + `subcommand`, enumerate the closed storage-type vocabulary (`marker-file, json-key, json-array, json-array-templated`), enumerate the closed mutation API set (`write_marker, delete_marker, set_json_key, delete_json_key, append_json_array, remove_json_array_value, run_feature_script`), enforce `oneOf [{required: [values]}, {required: [actions]}]`, and enumerate the closed alert color set (`red, green, yellow`). The shape is validated by `test/test-configuration-schema-shape.py`.

43. **`validate_meta_contract` library function (Plan A foundation).** `.claude/features/contract/lib/checks.py` MUST export `validate_meta_contract(feature_dir) -> CheckResult` that reads `<feature_dir>/feature.json`, validates each present meta-contract section (`manifest`, `runtime`, `configuration`) against its schema's rules, and returns a `CheckResult` whose `messages` enumerate every error encountered. Sections are optional — a feature.json with none of them validates successfully. The CLI shim at `.claude/features/contract/scripts/validate-meta-contract.py` mirrors the `validate-feature.py` pattern (thin shim; exit 0 pass / 1 validation error / 2 invocation error). Implementation is hand-rolled stdlib-only (no `jsonschema` dependency). Validation is enforced by `test/test-validate-meta-contract-{manifest,runtime,configuration,cli}.py`.
```

- [ ] **Step 2: Bump contract version**

Open `.claude/features/contract/docs/spec/spec.md` frontmatter. Change:

```yaml
version: 1.21.0
```

to:

```yaml
version: 1.22.0
```

Open `.claude/features/contract/feature.json`. Change its `version` field to `"1.22.0"`.

If the contract feature has a `docs/spec/contract.md` with its own `version` frontmatter field, update that to `1.22.0` as well (per the rabbit-cage Inv 58 three-way alignment pattern — verify whether contract has the same alignment rule).

- [ ] **Step 3: Run the full contract test suite one more time**

Run: `python3 .claude/features/contract/test/run.py`  
Expected: all PASS, exit 0. The spec/version changes should not break any test.

If `check-invariant-monotonic-order` (test for numbered-list monotonic ordering) fires: verify the four new invariants are numbered 40, 41, 42, 43 in order. If not, fix the numbering before committing.

- [ ] **Step 4: Commit**

```bash
git add .claude/features/contract/docs/spec/spec.md .claude/features/contract/feature.json
git commit -m "docs(contract): document Plan A meta-contract foundation (Inv 40-43)

Adds invariants for manifest/runtime/configuration schemas and the
validate_meta_contract library function. Version bump 1.21.0 -> 1.22.0."
```

---

## Plan complete — verification checklist

- [ ] All 10 tasks committed in order
- [ ] `python3 .claude/features/contract/test/run.py` exits 0
- [ ] `git log --oneline -10` shows the 10 commits in expected order
- [ ] No existing feature.json file rejected by the updated schema (the additions are purely optional)
- [ ] `.claude/features/contract/scripts/validate-meta-contract.py` runs against every existing feature dir without error (none have meta-contract sections yet, so all should validate)

Spot-check command:
```bash
for d in .claude/features/*/; do
  python3 .claude/features/contract/scripts/validate-meta-contract.py "$d" || echo "FAILED: $d"
done
```

Expected output: each feature dir prints "meta-contract sections valid (or absent)" and exits 0.

---

## What this plan does NOT do

Explicitly out of scope (deferred to subsequent plans):
- **Plan B**: implement the publish, runtime, mutation, and content-producer API libraries (currently just schemas + validator; no code that USES the APIs yet)
- **Plan C**: rewrite rabbit-cage as a dispatcher service
- **Plan D**: scaffold the rabbit-config feature
- **Plan E**: migrate each existing feature's `feature.json` to declare its own MANIFEST/RUNTIME/CONFIGURATION
- **Plan F**: drop `build-contract.json` and `rabbit-print-messages.json`, remove named message wrappers, end-to-end validation

After this plan lands, the system behaves identically to before — the meta-contract foundation is in place but nothing yet declares or consumes the new sections.
