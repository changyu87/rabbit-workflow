#!/usr/bin/env python3
"""Inv 57 (issue #418) — agent manifest item renamed tdd-subagent -> rabbit-tdd-subagent.

End-to-end coverage for the AGENT-name rename:
  - source agent file is agents/rabbit-tdd-subagent.md with
    `name: rabbit-tdd-subagent` frontmatter; legacy agents/tdd-subagent.md gone.
  - feature.json publish_agent manifest entry sources the renamed agent file.
  - contract `provides.agents` names the renamed source path.
  - run_publish_loop (manifest-driven) deploys to
    .claude/agents/rabbit-tdd-subagent.md (and NOT the legacy basename).

The script/feature-dir names (dispatch-tdd-subagent.py, tdd-step.py, the
feature directory, and the agent-adjacent .claude/agents/tdd-subagent/scripts/
deploy dir) are deliberately UNCHANGED; this test asserts they keep their
tdd-subagent names so the rename stays scoped to the agent manifest item.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature lifecycle management is natively
    handled by Claude Code's workflow mechanism.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / "install.py"
FEATURE_DIR = REPO / ".claude/features/tdd-subagent"
CONTRACT_DIR = REPO / ".claude/features/contract"

NEW_AGENT_SOURCE_REL = "agents/rabbit-tdd-subagent.md"
OLD_AGENT_SOURCE_REL = "agents/tdd-subagent.md"
NEW_AGENT_DEPLOY_REL = ".claude/agents/rabbit-tdd-subagent.md"
OLD_AGENT_DEPLOY_REL = ".claude/agents/tdd-subagent.md"
# script deploy dir keeps its tdd-subagent name (NOT renamed)
SCRIPTS_DEPLOY_DIR_REL = ".claude/agents/tdd-subagent/scripts"

passed = failed = 0


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg: str) -> None:
    global failed
    failed += 1
    print(f"  FAIL {msg}")


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- source-side assertions -------------------------------------------------
new_agent = FEATURE_DIR / NEW_AGENT_SOURCE_REL
old_agent = FEATURE_DIR / OLD_AGENT_SOURCE_REL
if new_agent.is_file():
    ok("inv57: agents/rabbit-tdd-subagent.md exists")
else:
    ko("inv57: agents/rabbit-tdd-subagent.md missing")
if not old_agent.exists():
    ok("inv57: legacy agents/tdd-subagent.md removed")
else:
    ko("inv57: legacy agents/tdd-subagent.md still present")

if new_agent.is_file():
    text = new_agent.read_text()
    if "name: rabbit-tdd-subagent" in text:
        ok("inv57: agent frontmatter declares name: rabbit-tdd-subagent")
    else:
        ko("inv57: agent frontmatter missing name: rabbit-tdd-subagent")
    if "name: tdd-subagent\n" not in text:
        ok("inv57: agent frontmatter no longer declares name: tdd-subagent")
    else:
        ko("inv57: agent frontmatter still declares name: tdd-subagent")

# --- feature.json manifest assertions ---------------------------------------
data = json.loads((FEATURE_DIR / "feature.json").read_text())
manifest = data.get("manifest", [])
agent_entries = [
    e for e in manifest
    if isinstance(e, dict) and e.get("api") == "publish_agent"
]
if len(agent_entries) == 1:
    ok("inv57: exactly one publish_agent manifest entry")
    src = (agent_entries[0].get("args") or {}).get("source")
    if src == NEW_AGENT_SOURCE_REL:
        ok("inv57: publish_agent sources agents/rabbit-tdd-subagent.md")
    else:
        ko(f"inv57: publish_agent source is {src!r}, expected {NEW_AGENT_SOURCE_REL!r}")
else:
    ko(f"inv57: expected 1 publish_agent entry, found {len(agent_entries)}")

# script deploy dir kept its tdd-subagent name (NOT renamed)
script_dests = [
    (e.get("args") or {}).get("dest", "")
    for e in manifest
    if isinstance(e, dict) and e.get("api") == "publish_file"
]
if all(d.startswith(".claude/agents/tdd-subagent/scripts/") for d in script_dests) and script_dests:
    ok("inv57: publish_file script dests keep .claude/agents/tdd-subagent/scripts/ dir")
else:
    ko(f"inv57: publish_file script dests not under tdd-subagent scripts dir: {script_dests}")

# --- contract provides assertion --------------------------------------------
contract_text = (FEATURE_DIR / "specs/contract.md").read_text()
start = contract_text.index("{")
contract = json.loads(contract_text[start:contract_text.rindex("}") + 1])
provided_agents = contract.get("provides", {}).get("agents", [])
agent_paths = [a.get("path", "") for a in provided_agents]
if any(p.endswith("agents/rabbit-tdd-subagent.md") for p in agent_paths):
    ok("inv57: contract provides names agents/rabbit-tdd-subagent.md")
else:
    ko(f"inv57: contract provides agent paths missing renamed path: {agent_paths}")
if not any(p.endswith("agents/tdd-subagent.md") for p in agent_paths):
    ok("inv57: contract provides no longer names legacy agents/tdd-subagent.md")
else:
    ko("inv57: contract provides still names legacy agents/tdd-subagent.md")

# --- e2e deployment via manifest-driven publish loop -------------------------
install = _load_install()
with tempfile.TemporaryDirectory() as td:
    target = Path(td)
    (target / ".claude/features").mkdir(parents=True)
    shutil.copytree(CONTRACT_DIR, target / ".claude/features/contract")
    shutil.copytree(FEATURE_DIR, target / ".claude/features/tdd-subagent")

    failures = install.run_publish_loop(str(target))
    if failures == 0:
        ok("inv57: run_publish_loop reports 0 failures")
    else:
        ko(f"inv57: run_publish_loop reported {failures} failure(s)")

    new_deploy = target / NEW_AGENT_DEPLOY_REL
    old_deploy = target / OLD_AGENT_DEPLOY_REL
    if new_deploy.is_file():
        ok("inv57: deployed .claude/agents/rabbit-tdd-subagent.md present")
    else:
        ko("inv57: deployed .claude/agents/rabbit-tdd-subagent.md missing")
    if not old_deploy.exists():
        ok("inv57: legacy deployed .claude/agents/tdd-subagent.md not produced")
    else:
        ko("inv57: legacy deployed .claude/agents/tdd-subagent.md produced")

    scripts_dir = target / SCRIPTS_DEPLOY_DIR_REL
    if (scripts_dir / "dispatch-tdd-subagent.py").is_file() and (scripts_dir / "tdd-step.py").is_file():
        ok("inv57: scripts deployed under .claude/agents/tdd-subagent/scripts/")
    else:
        ko("inv57: scripts not deployed under .claude/agents/tdd-subagent/scripts/")


total = passed + failed
if failed == 0:
    print(f"PASS: {passed}/{total}")
    sys.exit(0)
print(f"FAIL: {failed}/{total}")
sys.exit(1)
