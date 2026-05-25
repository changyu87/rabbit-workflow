#!/usr/bin/env python3
# state_machine_helpers.py — shared fixture utilities for the state-machine
# test files that were absorbed from the retired tdd-state-machine feature
# at tdd-subagent v4.0.0. (Named distinctly from tdd-subagent's pre-existing
# _helpers.py, which serves a different purpose — driving the dispatch CLI.)
#
# Owner: rabbit-workflow team (tdd-subagent)
# Deprecation criterion: when test fixtures move to a dedicated package.
#
# Purpose: shared fixture utilities; flat-schema feature.json shape.
import json
import os


def make_feature_dir(parent_dir, name, tdd_state, *, run_exit=0):
    """Create a minimal feature directory with flat-schema feature.json.

    Writes:
      <parent_dir>/feature.json (flat schema)
      <parent_dir>/spec.md      (placeholder)
      <parent_dir>/contract.md  (placeholder)
      <parent_dir>/test/run.py  (Python runner that exits `run_exit`)
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
