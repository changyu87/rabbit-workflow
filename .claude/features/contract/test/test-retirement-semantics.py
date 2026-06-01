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
  (t4 RETIRED — rabbit-spec was revived as an active feature; the
   per-feature required:false assertion no longer applies. The general
   Inv 36(c) prose still governs how workspace-structure.json treats
   retired tombstones, but no current feature exercises that arm here.)
  t5: .claude/features/contract/workspace-structure.json declares `tdd-state-machine` as
      a feature node (post-consolidation home of tdd-step/context/drift-check).
  (t6 RETIRED in Plan F.1 — tdd-state-machine/publish.json deleted; the
   equivalent source pointer is asserted by tdd-state-machine's own
   test/test-manifest-shape.py against feature.json manifest.)

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
WS_STRUCTURE = os.path.join(REPO_ROOT, ".claude/features/contract/workspace-structure.json")

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


# t4 RETIRED — rabbit-spec was revived as an active feature; the
# per-feature required:false assertion no longer applies.


# t5: workspace-structure.json declares tdd-state-machine as a feature node
with open(WS_STRUCTURE) as f:
    ws = json.load(f)
features_node = next((n for n in ws["nodes"] if n["name"] == "features"), None)
if features_node is not None:
    feat_children = {c["name"]: c for c in features_node.get("children", [])}
    if "tdd-state-machine" in feat_children:
        ok(5, "workspace-structure.json declares tdd-state-machine feature node")
    else:
        ko(5, "workspace-structure.json missing tdd-state-machine feature node")
else:
    ko(5, "skipped: no features node")


# t6 RETIRED in Plan F.1 — tdd-state-machine/publish.json deleted; the
# equivalent source pointer assertion lives in tdd-state-machine's own
# test/test-manifest-shape.py against the feature.json manifest.


print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
