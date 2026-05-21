#!/usr/bin/env python3
"""test-retired-artifacts.py — consolidated retirement regressions.

Consolidates the unique assertions from three predecessor files (deleted in
CONTRACT-BACKLOG-30 F6 consolidation):
  - test-dead-relink-tests-deleted.py  (BUG-35 / Inv 21)
  - test-backlog-27-retirements.py     (CONTRACT-BACKLOG-27)
  - test-bug-41-cleanup.py             (CONTRACT-BUG-41)

Section A — dead relink tests are gone (BUG-35).
Section B — BACKLOG-27 retirement assertions (scripts/skill/lib/build entries).
Section C — BUG-41 cleanup audit (CheckResult dataclass, get_repo_root public,
            _PRODUCER_FIELDS derived from schema, no stale headers).

Non-interactive. Exits non-zero on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when these path-absence / library-shape checks fold
into a generic dead-code linter wired into the Stop hook.
"""

import dataclasses
import importlib.util
import json
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def load_checks():
    spec = importlib.util.spec_from_file_location("contract_lib_checks_retire", CHECKS_PATH)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Section A — BUG-35: dead relink tests are gone
# ---------------------------------------------------------------------------
print("Section A — BUG-35 relink-test retirement")
for n, rel in (("a1", "test-relink-no-skills.py"), ("a2", "test-relink.py")):
    p = os.path.join(TEST_DIR, rel)
    if os.path.exists(p):
        ko(n, f"dead test still present: {p}")
    else:
        ok(n, f"{rel} has been deleted")

# a3: no remaining test file references the deleted scripts/relink.sh
# (test-build-contract.py is allowed because it asserts the ABSENCE of relink.sh
# per Inv 11; this file is also allowed because its docstring names it.)
SELF = os.path.basename(__file__)
ALLOWED = {SELF, "test-build-contract.py"}
offenders = []
for fname in os.listdir(TEST_DIR):
    if not fname.startswith("test-") or not fname.endswith(".py"):
        continue
    if fname in ALLOWED:
        continue
    try:
        with open(os.path.join(TEST_DIR, fname)) as f:
            if "scripts/relink.sh" in f.read():
                offenders.append(fname)
    except OSError:
        continue
if offenders:
    ko("a3", f"tests still reference deleted scripts/relink.sh: {offenders}")
else:
    ok("a3", "no test file references scripts/relink.sh")


# ---------------------------------------------------------------------------
# Section B — CONTRACT-BACKLOG-27 retirement set
# ---------------------------------------------------------------------------
print("Section B — CONTRACT-BACKLOG-27 retirement set")
DELETED_PATHS = [
    ("b1", "scripts/dispatch-feature-edit.py"),
    ("b2", "scripts/workspace-map.py"),
    ("b3", "scripts/enforcement/check-no-main-edits.py"),
    ("b4", "scripts/enforcement/check-opus-for-planning-agents.py"),
]
for n, rel in DELETED_PATHS:
    p = os.path.join(FEATURE_DIR, rel)
    if os.path.exists(p):
        ko(n, f"{rel} still present at {p}")
    else:
        ok(n, f"{rel} is absent")

# b5: source skill dir absent
src_skill = os.path.join(FEATURE_DIR, "skills/rabbit-workspace-map")
if os.path.exists(src_skill):
    ko("b5", f"source skill dir still present: {src_skill}")
else:
    ok("b5", "skills/rabbit-workspace-map/ source dir is absent")

# b6: deployed skill dir absent
deployed_skill = os.path.join(REPO_ROOT, ".claude/skills/rabbit-workspace-map")
if os.path.exists(deployed_skill):
    ko("b6", f"deployed skill dir still present: {deployed_skill}")
else:
    ok("b6", ".claude/skills/rabbit-workspace-map/ deployed dir is absent")

# b7: build-contract.json does not declare rabbit-workspace-map skill
bc_path = os.path.join(FEATURE_DIR, "build-contract.json")
with open(bc_path) as f:
    bc = json.load(f)
ws_entries = [
    t for t in bc.get("targets", [])
    if "rabbit-workspace-map" in t.get("name", "")
    or "rabbit-workspace-map" in t.get("source", "")
    or "rabbit-workspace-map" in t.get("destination", "")
]
if ws_entries:
    ko("b7", f"build-contract.json still declares rabbit-workspace-map: {[e.get('name') for e in ws_entries]}")
else:
    ok("b7", "build-contract.json declares no rabbit-workspace-map entry")

# b8: lib/checks.py does not export retired check functions
checks = load_checks()
if checks is None:
    ko("b8", f"could not import {CHECKS_PATH}")
else:
    retired = ["check_no_main_edits", "check_opus_for_planning_agents"]
    exported_retired = [name for name in retired if hasattr(checks, name)]
    if exported_retired:
        ko("b8", f"lib/checks.py still exports retired functions: {exported_retired}")
    else:
        ok("b8", "lib/checks.py does not export retired check functions")


# ---------------------------------------------------------------------------
# Section C — BUG-41 cleanup audit
# ---------------------------------------------------------------------------
print("Section C — BUG-41 cleanup audit")
if checks is None:
    ko("c0", "checks module not loaded (skipping section C)")
else:
    # c1: CheckResult is a @dataclass with exactly {passed, messages}
    if hasattr(checks, "CheckResult"):
        cls = checks.CheckResult
        if dataclasses.is_dataclass(cls):
            ok("c1a", "CheckResult is a @dataclass")
            fields = {f.name for f in dataclasses.fields(cls)}
            if fields == {"passed", "messages"}:
                ok("c1b", "CheckResult dataclass fields are exactly {passed, messages}")
            else:
                ko("c1b", f"CheckResult fields are {fields}, expected {{'passed','messages'}}")
        else:
            ko("c1a", f"CheckResult is not a @dataclass (type={type(cls).__name__})")
    else:
        ko("c1a", "CheckResult class missing")

    # c2: get_repo_root is public
    if hasattr(checks, "get_repo_root") and callable(checks.get_repo_root):
        ok("c2", "get_repo_root is a public callable in lib.checks")
    else:
        ko("c2", "get_repo_root (public) missing from lib.checks")

    # c3: _PRODUCER_FIELDS derived from bug.json.schema.json
    SCHEMA_PATH = os.path.join(FEATURE_DIR, "schemas", "bug.json.schema.json")
    with open(SCHEMA_PATH) as f:
        bug_schema = json.load(f)
    schema_props = set(bug_schema.get("properties", {}).keys())
    if not schema_props:
        ko("c3a", "bug.json.schema.json has no properties — cannot validate derivation")
    else:
        ok("c3a", f"bug.json.schema.json defines {len(schema_props)} producer fields")
        if not hasattr(checks, "_PRODUCER_FIELDS"):
            ko("c3b", "_PRODUCER_FIELDS missing from lib.checks")
        elif checks._PRODUCER_FIELDS == schema_props:
            ok("c3b", "_PRODUCER_FIELDS == bug.json.schema.json properties")
        else:
            extra = checks._PRODUCER_FIELDS - schema_props
            missing = schema_props - checks._PRODUCER_FIELDS
            ko("c3b", f"_PRODUCER_FIELDS not derived from schema: extra={extra}, missing={missing}")

        # c3c: no hardcoded literal in checks.py
        with open(CHECKS_PATH) as f:
            src = f.read()
        hardcoded_marker = '"name", "title", "status", "severity"'
        if hardcoded_marker in src:
            ko("c3c", "checks.py still contains a hardcoded producer-field set literal")
        else:
            ok("c3c", "checks.py does not contain a hardcoded producer-field set literal")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
