#!/usr/bin/env python3
"""test-retirement-semantics.py — e2e regression for BUG-40 Inv 35/36.

Covers:
  t1: feature.json.schema.json declares the `status` field with enum
      ["active", "retired"].
  t2: validate-feature.py short-circuits (exits 0) on a feature whose
      feature.json carries status=retired, even when other required
      structural files (spec.md, contract.md, test/run.py) are absent.
  t3: validate-feature.py still fails (exit 1) on a feature whose
      feature.json carries status=active and is missing required files.
  t4: .claude/workspace-structure.json marks the retired feature
      `rabbit-spec` as required: false so workspace-map.py --audit does
      not emit error-severity findings for the tombstone directory.
      The `rabbit-feature-scope` directory was fully retired and removed
      (no tombstone), so its node is also absent from workspace-structure.json.
  t5: .claude/workspace-structure.json declares `tdd-state-machine` as
      a feature node (post-consolidation home of tdd-step/context/drift-check).
  t6: tdd-state-machine/publish.json tdd-step.py source points to tdd-state-machine scripts/

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when retirement semantics are absorbed into a native
rabbit CLI lifecycle command and validated there.
"""

import json
import os
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))

SCHEMA = os.path.join(FEATURE_DIR, "schemas/feature.json.schema.json")
VALIDATE = os.path.join(FEATURE_DIR, "scripts/validate-feature.py")
WS_STRUCTURE = os.path.join(REPO_ROOT, ".claude/workspace-structure.json")

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def ko(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}")
    failed += 1


print("test-retirement-semantics.py")

# t1: schema declares `status` with enum [active, retired]
with open(SCHEMA) as f:
    schema = json.load(f)
status_prop = schema.get("properties", {}).get("status")
if status_prop is None:
    ko(1, "feature.json.schema.json does not declare 'status' property")
else:
    enum = status_prop.get("enum", [])
    if set(enum) == {"active", "retired"}:
        ok(1, "feature.json.schema.json status enum = [active, retired]")
    else:
        ko(1, f"feature.json.schema.json status enum is {enum!r}, expected [active, retired]")


# t2: validate-feature.py short-circuits on status=retired (no spec/contract/test)
with tempfile.TemporaryDirectory() as td:
    retired_dir = os.path.join(td, "fake-retired")
    os.makedirs(retired_dir)
    with open(os.path.join(retired_dir, "feature.json"), "w") as f:
        json.dump({
            "name": "fake-retired",
            "version": "1.0.0",
            "owner": "test",
            "tdd_state": "test-green",
            "summary": "tombstone",
            "status": "retired",
            "surface": {"hooks": [], "commands": [], "agents": [], "skills": []},
            "deprecation_criterion": "n/a",
        }, f)
    result = subprocess.run(
        [sys.executable, VALIDATE, retired_dir],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        ok(2, "validate-feature.py exits 0 on status=retired without spec/contract/test")
    else:
        ko(2, f"validate-feature.py exited {result.returncode} on retired feature: "
              f"stdout={result.stdout!r} stderr={result.stderr!r}")


# t3: validate-feature.py still fails on active feature missing required files
with tempfile.TemporaryDirectory() as td:
    active_dir = os.path.join(td, "fake-active")
    os.makedirs(active_dir)
    with open(os.path.join(active_dir, "feature.json"), "w") as f:
        json.dump({
            "name": "fake-active",
            "version": "1.0.0",
            "owner": "test",
            "tdd_state": "test-green",
            "summary": "active feature with no spec/contract/test",
            "status": "active",
            "surface": {"hooks": [], "commands": [], "agents": [], "skills": []},
            "deprecation_criterion": "n/a",
        }, f)
    result = subprocess.run(
        [sys.executable, VALIDATE, active_dir],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        ok(3, "validate-feature.py exits non-zero on active feature missing structural files")
    else:
        ko(3, "validate-feature.py incorrectly passed an active feature missing spec/contract/test")


# t4: workspace-structure.json marks the rabbit-spec tombstone as required:false,
# and the fully-retired rabbit-feature-scope directory is absent entirely.
with open(WS_STRUCTURE) as f:
    ws = json.load(f)
features_node = next((n for n in ws["nodes"] if n["name"] == "features"), None)
if features_node is None:
    ko(4, "workspace-structure.json missing 'features' top-level node")
else:
    feat_children = {c["name"]: c for c in features_node.get("children", [])}
    rs = feat_children.get("rabbit-spec")
    rfs = feat_children.get("rabbit-feature-scope")
    if rs is None:
        ko(4, "workspace-structure.json missing rabbit-spec tombstone node")
    elif rs.get("required") is True:
        ko(4, f"workspace-structure.json marks rabbit-spec tombstone as required: "
              f"rabbit-spec.required={rs.get('required')!r}")
    elif rfs is not None:
        ko(4, "workspace-structure.json must NOT declare rabbit-feature-scope "
              "(directory was fully retired and removed; no tombstone)")
    else:
        ok(4, "workspace-structure.json marks rabbit-spec tombstone as required:false "
              "and omits the fully-retired rabbit-feature-scope")


# t5: workspace-structure.json declares tdd-state-machine as a feature node
if features_node is not None:
    feat_children = {c["name"]: c for c in features_node.get("children", [])}
    if "tdd-state-machine" in feat_children:
        ok(5, "workspace-structure.json declares tdd-state-machine feature node")
    else:
        ko(5, "workspace-structure.json missing tdd-state-machine feature node")
else:
    ko(5, "skipped: no features node")


# t6: tdd-state-machine/publish.json tdd-step.py source points to tdd-state-machine scripts/
TDD_SM_PUBLISH = os.path.join(REPO_ROOT, ".claude/features/tdd-state-machine/publish.json")
if os.path.isfile(TDD_SM_PUBLISH):
    with open(TDD_SM_PUBLISH) as f:
        pub = json.load(f)
    tdd_step_entry = next(
        (t for t in pub.get("targets", [])
         if t.get("name") == "agents/tdd-subagent/scripts/tdd-step.py"),
        None,
    )
    if tdd_step_entry is None:
        ko(6, "tdd-state-machine/publish.json missing tdd-step.py target")
    elif tdd_step_entry.get("source") != "scripts/tdd-step.py":
        ko(6, f"tdd-step.py source = {tdd_step_entry.get('source')!r}, expected 'scripts/tdd-step.py'")
    else:
        ok(6, "tdd-state-machine/publish.json tdd-step.py source is 'scripts/tdd-step.py'")
else:
    ko(6, f"tdd-state-machine/publish.json not found at {TDD_SM_PUBLISH}")


print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
