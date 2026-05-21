#!/usr/bin/env python3
# test-build-contract.py — verify build-contract.json, its schema, and relink.sh deletion.
#
# t1: build-contract.json exists
# t2: build-contract.json is valid JSON
# t3: build-contract.json validates against build-contract.schema.json
# t4: all copy-file source paths declared in build-contract.json exist on disk
# t5: relink.sh does NOT exist at scripts/relink.sh

import os
import sys
import json
import subprocess

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

CONTRACT = os.path.join(FEATURE_DIR, "build-contract.json")
SCHEMA = os.path.join(FEATURE_DIR, "schemas/build-contract.schema.json")
RELINK = os.path.join(FEATURE_DIR, "scripts/relink.sh")

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def fail_t(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}")
    failed += 1


print("test-build-contract.py")

# t1: build-contract.json exists
if os.path.isfile(CONTRACT):
    ok(1, "build-contract.json exists")
else:
    fail_t(1, f"build-contract.json does not exist at {CONTRACT}")

# t2: build-contract.json is valid JSON
contract_data = None
if os.path.isfile(CONTRACT):
    try:
        contract_data = json.load(open(CONTRACT))
        ok(2, "build-contract.json is valid JSON")
    except (json.JSONDecodeError, OSError):
        fail_t(2, "build-contract.json is not valid JSON")
else:
    fail_t(2, "build-contract.json is not valid JSON (file missing)")

# t3: build-contract.json validates against build-contract.schema.json
if contract_data is not None and os.path.isfile(SCHEMA):
    valid = False
    try:
        import jsonschema
        schema = json.load(open(SCHEMA))
        jsonschema.validate(contract_data, schema)
        valid = True
    except ImportError:
        # Fallback: check required fields manually
        try:
            schema = json.load(open(SCHEMA))
            required = schema.get("required", [])
            for field in required:
                if field not in contract_data:
                    raise ValueError(f"missing required field: {field}")
            targets = contract_data.get("targets", [])
            if not isinstance(targets, list):
                raise ValueError("targets must be a list")
            for t in targets:
                for req in ["name", "type", "destination", "check_on_stop"]:
                    if req not in t:
                        raise ValueError(f"target missing field: {req}")
                if t["type"] not in ["copy-file", "generate-claude-md"]:
                    raise ValueError(f"invalid type: {t['type']}")
                if t["type"] == "copy-file" and "source" not in t:
                    raise ValueError("copy-file target missing 'source'")
            valid = True
        except (ValueError, json.JSONDecodeError, OSError):
            valid = False
    except Exception:
        valid = False

    if valid:
        ok(3, "build-contract.json validates against build-contract.schema.json")
    else:
        fail_t(3, "build-contract.json does not validate against build-contract.schema.json")
else:
    fail_t(3, "build-contract.json validates against build-contract.schema.json (file(s) missing)")

# t4: all copy-file source paths declared in build-contract.json exist on disk
if contract_data is not None:
    t4_fail = False
    for t in contract_data.get("targets", []):
        if t.get("type") == "copy-file":
            src = t["source"]
            full = os.path.join(REPO_ROOT, src) if REPO_ROOT else src
            if not os.path.exists(full):
                fail_t(4, f"copy-file source does not exist: {src}")
                t4_fail = True
    if not t4_fail:
        ok(4, "all copy-file source paths exist on disk")
else:
    fail_t(4, "all copy-file source paths exist on disk (build-contract.json missing or invalid)")

# t5: relink.sh does NOT exist
if not os.path.isfile(RELINK):
    ok(5, "relink.sh does not exist at scripts/relink.sh")
else:
    fail_t(5, f"relink.sh still exists at {RELINK} (should be deleted)")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
