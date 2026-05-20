#!/usr/bin/env python3
"""test-bug-41-cleanup.py — CONTRACT-BUG-41 audit-finding assertions.

End-to-end tests for the four lib/checks.py cleanup items in BUG-41:

  t1  CheckResult is a @dataclass (Inv 44(a) literal compliance).
  t2  get_repo_root is a public (non-underscore) function.
  t3  _PRODUCER_FIELDS in check_template_producer_consistency is derived
       from a live source (bug.json.schema.json), not a hardcoded literal.
  t4  test-bug-fixes-cycle.py header/comments do not reference deleted
       scripts as live (render-template.py, workspace-map.py,
       check-opus-for-planning-agents.py must only appear as moot/deleted
       notices).

Non-interactive. Exits non-zero on failure.
"""

import dataclasses
import importlib.util
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")
SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "bug.json.schema.json")
CYCLE_TEST = os.path.join(FEATURE_DIR, "test", "test-bug-fixes-cycle.py")

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS {n}: {msg}")
    passed += 1


def ko(n, msg):
    global failed
    print(f"  FAIL {n}: {msg}", file=sys.stderr)
    failed += 1


def load_checks():
    spec = importlib.util.spec_from_file_location(
        "contract_lib_checks_bug41", CHECKS_PATH
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checks = load_checks()
if checks is None:
    ko("t0", f"could not import {CHECKS_PATH}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(1)

# t1: CheckResult is a @dataclass
if not hasattr(checks, "CheckResult"):
    ko("t1", "CheckResult class missing")
else:
    cls = checks.CheckResult
    if dataclasses.is_dataclass(cls):
        ok("t1a", "CheckResult is a @dataclass")
        fields = {f.name for f in dataclasses.fields(cls)}
        if fields == {"passed", "messages"}:
            ok("t1b", "CheckResult dataclass fields are exactly {passed, messages}")
        else:
            ko("t1b", f"CheckResult fields are {fields}, expected {{'passed','messages'}}")
    else:
        ko("t1a", f"CheckResult is not a @dataclass (type={type(cls).__name__})")

# t2: get_repo_root is public
if hasattr(checks, "get_repo_root") and callable(checks.get_repo_root):
    ok("t2", "get_repo_root is a public callable in lib.checks")
else:
    ko("t2", "get_repo_root (public) missing from lib.checks")

# t3: _PRODUCER_FIELDS derived from live source (bug.json.schema.json properties)
import json
with open(SCHEMA_PATH) as f:
    bug_schema = json.load(f)
schema_props = set(bug_schema.get("properties", {}).keys())
if not schema_props:
    ko("t3a", "bug.json.schema.json has no properties — cannot validate derivation")
else:
    ok("t3a", f"bug.json.schema.json defines {len(schema_props)} producer fields")

    # The implementation must expose the derived set so the test can verify
    # the derivation actually happened (not just hardcoded duplication).
    if not hasattr(checks, "_PRODUCER_FIELDS"):
        ko("t3b", "_PRODUCER_FIELDS missing from lib.checks")
    else:
        # Live source = bug.json.schema.json properties. The producer set must
        # be exactly the schema property set (any subsequent field added to
        # the schema flows through automatically).
        if checks._PRODUCER_FIELDS == schema_props:
            ok("t3b", "_PRODUCER_FIELDS == bug.json.schema.json properties")
        else:
            extra = checks._PRODUCER_FIELDS - schema_props
            missing = schema_props - checks._PRODUCER_FIELDS
            ko(
                "t3b",
                f"_PRODUCER_FIELDS not derived from schema: "
                f"extra={extra}, missing={missing}",
            )

    # Source-level assertion: no hardcoded set literal containing producer
    # field names in checks.py.
    with open(CHECKS_PATH) as f:
        src = f.read()
    hardcoded_marker = '"name", "title", "status", "severity"'
    if hardcoded_marker in src:
        ko("t3c", "checks.py still contains a hardcoded producer-field set literal")
    else:
        ok("t3c", "checks.py does not contain a hardcoded producer-field set literal")

# t4: stale references in test-bug-fixes-cycle.py header are clean
with open(CYCLE_TEST) as f:
    cycle_src = f.read()
# Stale references to deleted scripts must only appear in deletion/moot notices,
# not as the original docstring header that claimed live assertions.
# A clean header lists deletions explicitly. Reject any docstring listing
# that names render-template.py as an active behaviour.
header_end = cycle_src.find('"""', cycle_src.find('"""') + 3)
header = cycle_src[:header_end] if header_end != -1 else cycle_src

bad_in_header = []
for stale in ("render-template", "workspace-map.py", "check-opus-for-planning-agents"):
    # Allow mention only if explicitly tagged as deleted/moot.
    if stale in header:
        # The line must say 'deleted', 'moot', or 'removed' nearby.
        idx = header.find(stale)
        ctx = header[max(0, idx - 80) : idx + 120].lower()
        if not any(t in ctx for t in ("deleted", "moot", "removed", "retired")):
            bad_in_header.append(stale)
if bad_in_header:
    ko(
        "t4",
        f"test-bug-fixes-cycle.py docstring still names stale scripts as live: {bad_in_header}",
    )
else:
    ok("t4", "test-bug-fixes-cycle.py docstring references to stale scripts tagged as deleted/moot")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
