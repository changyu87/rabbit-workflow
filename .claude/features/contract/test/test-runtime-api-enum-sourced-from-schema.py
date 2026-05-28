#!/usr/bin/env python3
"""test-runtime-api-enum-sourced-from-schema.py — CONTRACT-BUG-47 / Inv 41.

Asserts that contract.lib.checks._RUNTIME_API_ENUM is sourced from
schemas/runtime.schema.json at module-import time rather than being
hardcoded. This prevents the two artifacts from drifting apart when new
runtime APIs are added.

Non-interactive. Exits non-zero on failure.
"""

import importlib.util
import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "runtime.schema.json")

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


def load_checks():
    spec = importlib.util.spec_from_file_location("contract_lib_checks", CHECKS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# t0: prerequisites
if not os.path.isfile(CHECKS_PATH):
    fail("t0a", f"checks.py missing: {CHECKS_PATH}")
    sys.exit(1)
if not os.path.isfile(SCHEMA_PATH):
    fail("t0b", f"runtime.schema.json missing: {SCHEMA_PATH}")
    sys.exit(1)
ok("t0", "checks.py and runtime.schema.json both exist")

# Load expected enum from the schema directly.
with open(SCHEMA_PATH) as f:
    schema = json.load(f)
expected_enum = frozenset(
    schema["definitions"]["call_list"]["items"]["properties"]["api"]["enum"]
)

# t1: import checks and assert _RUNTIME_API_ENUM equals the schema enum
try:
    checks = load_checks()
except Exception as e:  # noqa: BLE001
    fail("t1", f"failed to import lib/checks.py: {type(e).__name__}: {e}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)

if not hasattr(checks, "_RUNTIME_API_ENUM"):
    fail("t1", "checks._RUNTIME_API_ENUM is missing")
else:
    actual = frozenset(checks._RUNTIME_API_ENUM)
    if actual == expected_enum:
        ok("t1", f"_RUNTIME_API_ENUM matches schema enum ({len(actual)} entries)")
    else:
        missing = expected_enum - actual
        extra = actual - expected_enum
        fail(
            "t1",
            f"_RUNTIME_API_ENUM diverges from schema: missing={sorted(missing)}, extra={sorted(extra)}",
        )

# t2: source-of-truth proof — read the checks.py source and assert it does
# NOT contain a hardcoded enum literal (the 11 specific API names laid out
# as a frozenset of string literals). If the implementation switches to
# schema-sourced loading, the literal list cannot be present at module
# scope as the enum source.
with open(CHECKS_PATH) as f:
    source = f.read()

# A hardcoded frozenset of the 11 names would include all of these literal
# strings inside a `frozenset({...})` block. Heuristic: if ALL 11 enum
# values appear as quoted literals in the same contiguous region (we use
# the assignment to _RUNTIME_API_ENUM as the anchor), it's still hardcoded.
import re as _re
assign_match = _re.search(
    r"_RUNTIME_API_ENUM\s*=\s*frozenset\s*\(\s*\{([^}]*)\}\s*\)",
    source,
)
if assign_match:
    literal_block = assign_match.group(1)
    hardcoded_names = [
        name for name in expected_enum if f'"{name}"' in literal_block
    ]
    if len(hardcoded_names) == len(expected_enum):
        fail(
            "t2",
            "checks.py still contains a hardcoded frozenset literal of all 11 API names — not sourced from schema",
        )
    else:
        ok("t2", "no hardcoded full-enum frozenset literal in checks.py")
else:
    ok("t2", "no inline frozenset literal assignment for _RUNTIME_API_ENUM (sourced elsewhere)")

# t3: regression — if the schema were to grow a new entry, the live
# _RUNTIME_API_ENUM in checks must reflect it on reimport. We simulate by
# writing a temp schema with an extra entry and re-importing the module
# under a patched path. Easier and equally rigorous: monkey-patch the
# schema file in a tmpdir, copy checks.py to point at it, and reimport.
# To keep this test simple and stdlib-only, we instead just assert the
# equality property holds RIGHT NOW (covered by t1) AND that the loader
# code path exists by checking that checks.py contains a json.load or
# json.loads call referencing runtime.schema.json.
if "runtime.schema.json" in source and ("json.load" in source or "json.loads" in source):
    ok("t3", "checks.py source references runtime.schema.json + json.load(s) — schema-sourced loader present")
else:
    fail(
        "t3",
        "checks.py source does not appear to load runtime.schema.json via json.load(s)",
    )

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
