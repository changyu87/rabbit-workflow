#!/usr/bin/env python3
"""Tests for tdd-subagent agent definition."""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


def test_agent_source_exists():
    path = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
    assert os.path.isfile(path), f"Source agent definition missing: {path}"


def test_agent_deployed_exists():
    path = os.path.join(REPO_ROOT, ".claude", "agents", "tdd-subagent.md")
    assert os.path.isfile(path), f"Deployed agent definition missing: {path}"


def test_agent_copies_identical():
    src = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
    dst = os.path.join(REPO_ROOT, ".claude", "agents", "tdd-subagent.md")
    with open(src) as f:
        src_content = f.read()
    with open(dst) as f:
        dst_content = f.read()
    assert src_content == dst_content, "Source and deployed agent definitions differ"


def test_agent_has_opus_model():
    path = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
    with open(path) as f:
        content = f.read()
    assert "model: opus" in content, "Agent definition must declare model: opus"


def test_agent_has_name():
    path = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
    with open(path) as f:
        content = f.read()
    assert "name: tdd-subagent" in content, "Agent definition must have name: tdd-subagent"


def test_agent_mentions_e2e_rule():
    path = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
    with open(path) as f:
        content = f.read()
    assert "end-to-end test" in content.lower() or "e2e" in content.lower(), \
        "Agent definition must state E2E test rule"


def test_build_contract_has_agent_entry():
    import json
    pub_path = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent", "publish.json")
    with open(pub_path) as f:
        bc = json.load(f)
    entries = [t for t in bc.get("targets", [])
               if t.get("destination") == ".claude/agents/tdd-subagent.md"]
    assert len(entries) == 1, "tdd-subagent/publish.json must have exactly one entry for agents/tdd-subagent.md"
    assert entries[0].get("check_on_stop") is True, "Entry must have check_on_stop: true"


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
