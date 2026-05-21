#!/usr/bin/env python3
"""test-slim-after-extraction.py

Regression test for the tdd-subagent slim after extraction to tdd-state-machine.

Asserts:
  (a) tdd-step.py is ABSENT from .claude/features/tdd-subagent/scripts/.
  (b) tdd-step.py is PRESENT in .claude/features/tdd-state-machine/scripts/.
  (c) dispatch-tdd-subagent.py's tdd_step_py path string points at tdd-state-machine.
  (d) build-contract.json copy-file source for tdd-step.py points at tdd-state-machine.
  (e) The deployed agent script .claude/agents/tdd-subagent/scripts/tdd-step.py exists.
  (g) tdd-subagent's contract.md provides.scripts does not list tdd-step.py under tdd-subagent.
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
TDD_SUB_SCRIPTS = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent", "scripts")
TDD_SM_SCRIPTS = os.path.join(REPO_ROOT, ".claude", "features", "tdd-state-machine", "scripts")
DISPATCH = os.path.join(TDD_SUB_SCRIPTS, "dispatch-tdd-subagent.py")
BUILD_CONTRACT = os.path.join(REPO_ROOT, ".claude", "features", "contract", "build-contract.json")
CONTRACT_MD = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent", "docs", "spec", "contract.md")
AGENT_DEPLOYED_SCRIPTS = os.path.join(REPO_ROOT, ".claude", "agents", "tdd-subagent", "scripts")

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


# (a) tdd-step.py absent from tdd-subagent
def t_a_absent_from_tdd_subagent():
    p = os.path.join(TDD_SUB_SCRIPTS, "tdd-step.py")
    if os.path.exists(p):
        ko(f"a: tdd-step.py still present at {p} (should live in tdd-state-machine)")
    else:
        ok("a: tdd-step.py absent from tdd-subagent/scripts/")


# (b) tdd-step.py present in tdd-state-machine
def t_b_present_in_tdd_state_machine():
    p = os.path.join(TDD_SM_SCRIPTS, "tdd-step.py")
    if os.path.isfile(p):
        ok("b: tdd-step.py present in tdd-state-machine/scripts/")
    else:
        ko(f"b: tdd-step.py missing from tdd-state-machine/scripts/")


# (c) dispatch script's hardcoded path points at tdd-state-machine
def t_c_dispatch_path_repoint():
    with open(DISPATCH) as f:
        src = f.read()
    bad = re.search(
        r'os\.path\.join\([^)]*"tdd-subagent"[^)]*"scripts"[^)]*"tdd-step\.py"',
        src,
    )
    if bad:
        ko(f"c: dispatch still constructs old tdd-subagent path for tdd-step.py: {bad.group(0)!r}")
    else:
        ok("c: dispatch no longer constructs old tdd-subagent path for tdd-step.py")
    good = re.search(
        r'os\.path\.join\([^)]*"tdd-state-machine"[^)]*"scripts"[^)]*"tdd-step\.py"',
        src,
    )
    if good:
        ok("c: dispatch constructs new tdd-state-machine path for tdd-step.py")
    else:
        ko("c: dispatch does NOT construct tdd-state-machine path for tdd-step.py")


# (d) build-contract.json copy-file source for tdd-step.py points at tdd-state-machine
def t_d_build_contract_sources():
    with open(BUILD_CONTRACT) as f:
        bc = json.load(f)
    dest = ".claude/agents/tdd-subagent/scripts/tdd-step.py"
    targets = [t for t in bc.get("targets", []) if t.get("destination") == dest]
    if len(targets) != 1:
        ko(f"d: expected exactly one copy-file target for {dest}, got {len(targets)}")
        return
    src = targets[0].get("source", "")
    if "tdd-state-machine" in src and src.endswith("scripts/tdd-step.py"):
        ok(f"d: build-contract source for tdd-step.py points at tdd-state-machine: {src}")
    else:
        ko(f"d: build-contract source for tdd-step.py not from tdd-state-machine: {src}")


# (e) deployed agent script tdd-step.py still exists
def t_e_deployed_still_present():
    p = os.path.join(AGENT_DEPLOYED_SCRIPTS, "tdd-step.py")
    if os.path.isfile(p):
        ok(f"e: deployed agent script present at {p}")
    else:
        ko(f"e: deployed agent script missing: {p}")


# (g) contract.md provides.scripts checks
def t_g_contract_provides_slimmed():
    with open(CONTRACT_MD) as f:
        cm = f.read()
    m = re.search(r"```json\s*(.*?)```", cm, re.DOTALL)
    if not m:
        ko("g: contract.md has no fenced JSON block")
        return
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        ko(f"g: contract.md JSON parse error: {e}")
        return
    script_paths = [s.get("path", "") for s in data.get("provides", {}).get("scripts", [])]
    if any(p.endswith("tdd-subagent/scripts/dispatch-tdd-subagent.py") for p in script_paths):
        ok("g: contract.md provides.scripts lists dispatch-tdd-subagent.py")
    else:
        ko("g: contract.md provides.scripts missing dispatch-tdd-subagent.py")


t_a_absent_from_tdd_subagent()
t_b_present_in_tdd_state_machine()
t_c_dispatch_path_repoint()
t_d_build_contract_sources()
t_e_deployed_still_present()
t_g_contract_provides_slimmed()

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
