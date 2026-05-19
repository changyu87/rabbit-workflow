#!/usr/bin/env python3
"""Tests for tdd-subagent deployed agent scripts in .claude/agents/tdd-subagent/scripts/.

After the tdd-state-machine extraction, only dispatch-tdd-subagent.py is sourced
from this feature's scripts/ directory. tdd-step.py, tdd-context.py, and
tdd-drift-check.py are sourced from .claude/features/tdd-state-machine/scripts/
(verified by test-slim-after-extraction.py)."""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
FEATURE_SCRIPTS = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent", "scripts")
AGENT_SCRIPTS = os.path.join(REPO_ROOT, ".claude", "agents", "tdd-subagent", "scripts")
# Only the dispatch script lives in tdd-subagent's scripts/ after extraction.
OWNED_SCRIPTS = ["dispatch-tdd-subagent.py"]
# All four scripts must still be deployed to the agent scripts dir; the other
# three are sourced from tdd-state-machine (see build-contract.json).
DEPLOYED_SCRIPTS = ["tdd-step.py", "dispatch-tdd-subagent.py", "tdd-drift-check.py", "tdd-context.py"]


def test_agent_scripts_dir_exists():
    assert os.path.isdir(AGENT_SCRIPTS), f"Missing: {AGENT_SCRIPTS}"


def test_all_scripts_deployed():
    for s in DEPLOYED_SCRIPTS:
        path = os.path.join(AGENT_SCRIPTS, s)
        assert os.path.isfile(path), f"Missing deployed script: {s}"


def test_deployed_owned_scripts_match_source():
    """For scripts whose source still lives in tdd-subagent/scripts/, the
    deployed copy must match. tdd-state-machine-owned scripts are checked in
    that feature's tests."""
    for s in OWNED_SCRIPTS:
        src = os.path.join(FEATURE_SCRIPTS, s)
        dst = os.path.join(AGENT_SCRIPTS, s)
        with open(src) as f:
            src_content = f.read()
        with open(dst) as f:
            dst_content = f.read()
        assert src_content == dst_content, f"Drift detected: {s}"


def test_build_contract_has_all_script_entries():
    bc = os.path.join(REPO_ROOT, ".claude", "features", "contract", "build-contract.json")
    with open(bc) as f:
        data = json.load(f)
    destinations = {t["destination"] for t in data.get("targets", [])
                    if t.get("type") == "copy-file"}
    for s in DEPLOYED_SCRIPTS:
        expected = f".claude/agents/tdd-subagent/scripts/{s}"
        assert expected in destinations, f"Missing build-contract entry: {expected}"


def test_all_script_entries_have_check_on_stop():
    bc = os.path.join(REPO_ROOT, ".claude", "features", "contract", "build-contract.json")
    with open(bc) as f:
        data = json.load(f)
    for t in data.get("targets", []):
        if t.get("type") == "copy-file" and "agents/tdd-subagent/scripts" in t.get("destination", ""):
            assert t.get("check_on_stop") is True, f"Missing check_on_stop: {t['destination']}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
