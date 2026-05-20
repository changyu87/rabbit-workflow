#!/usr/bin/env python3
# test_helpers.py — shared fixture utilities for tdd-state-machine test suite.
#
# Owner: rabbit-workflow team (tdd-state-machine)
# Deprecation criterion: when test fixtures move to a dedicated package or
# the tdd-state-machine feature itself is retired.
#
# Purpose (BACKLOG-10): the legacy fixture function `fix(...)` was duplicated
# across multiple test files (historically `test-tdd-step.py`, `test-context.py`,
# `test-drift-check.py`; the latter two were retired in BACKLOG-7) and had
# drifted from the canonical flat-schema feature.json shape. This module is
# the single source of truth for the feature.json shape used by
# tdd-state-machine unit/e2e tests.
import json
import os


def make_feature_dir(parent_dir, name, tdd_state, *, run_exit=0):
    """Create a minimal feature directory with flat-schema feature.json.

    Writes:
      <parent_dir>/feature.json (flat schema)
      <parent_dir>/spec.md      (placeholder)
      <parent_dir>/contract.md  (placeholder)
      <parent_dir>/test/run.py  (Python runner that exits `run_exit`)

    The flat schema is the only canonical shape; the legacy nested form
    (`owner` as object, `deprecation.criterion` nested) is no longer
    produced here.
    """
    os.makedirs(os.path.join(parent_dir, "test"), exist_ok=True)
    feature_json = {
        "name": name,
        "version": "0.1.0",
        "owner": "test",
        "tdd_state": tdd_state,
        "summary": "test fixture",
        "surface": {"hooks": [], "commands": [], "skills": []},
        "deprecation_criterion": "fixture",
        "updated": "2026-05-18",
    }
    with open(os.path.join(parent_dir, "feature.json"), "w") as f:
        json.dump(feature_json, f, indent=2)
    with open(os.path.join(parent_dir, "spec.md"), "w") as f:
        f.write("spec\n")
    with open(os.path.join(parent_dir, "contract.md"), "w") as f:
        f.write("contract\n")
    run_py = os.path.join(parent_dir, "test", "run.py")
    with open(run_py, "w") as f:
        f.write(f"#!/usr/bin/env python3\nimport sys\nsys.exit({run_exit})\n")
    os.chmod(run_py, 0o755)
