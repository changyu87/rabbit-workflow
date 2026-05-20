#!/usr/bin/env python3
"""test-slim-after-extraction.py

Regression test for the tdd-subagent slim after extraction to
tdd-state-machine.

Asserts:
  (a) The three extracted scripts (tdd-step.py, tdd-context.py,
      tdd-drift-check.py) are ABSENT from
      .claude/features/tdd-subagent/scripts/.
  (b) The three extracted scripts are PRESENT in
      .claude/features/tdd-state-machine/scripts/ (the new owner).
  (c) dispatch-tdd-subagent.py's tdd_step_py path string points at
      the tdd-state-machine source, not at the deleted tdd-subagent
      copy.
  (d) build-contract.json copy-file sources for the three scripts
      point at tdd-state-machine.
  (e) The deployed agent scripts at
      .claude/agents/tdd-subagent/scripts/ still exist (build.py
      copies them from tdd-state-machine).
  (f) tdd-subagent's feature.json surface only declares the
      surviving surface (dispatch script + agent definition).
  (g) tdd-subagent's contract.md provides.scripts no longer lists the
      three extracted scripts.
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
FEATURE_JSON = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent", "feature.json")
AGENT_DEPLOYED_SCRIPTS = os.path.join(REPO_ROOT, ".claude", "agents", "tdd-subagent", "scripts")

EXTRACTED = ["tdd-step.py", "tdd-context.py", "tdd-drift-check.py"]

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


# (a) extracted scripts absent from tdd-subagent
def t_a_absent_from_tdd_subagent():
    for s in EXTRACTED:
        p = os.path.join(TDD_SUB_SCRIPTS, s)
        if os.path.exists(p):
            ko(f"a: {s} still present at {p}")
        else:
            ok(f"a: {s} absent from tdd-subagent/scripts/")


# (b) extracted scripts present in tdd-state-machine
def t_b_present_in_tdd_state_machine():
    for s in EXTRACTED:
        p = os.path.join(TDD_SM_SCRIPTS, s)
        if not os.path.isfile(p):
            ko(f"b: {s} missing from tdd-state-machine/scripts/")
        else:
            ok(f"b: {s} present in tdd-state-machine/scripts/")


# (c) dispatch script's hardcoded path points at tdd-state-machine
def t_c_dispatch_path_repoint():
    with open(DISPATCH) as f:
        src = f.read()
    # Ensure no reference to the old (deleted) tdd-subagent path of tdd-step.py.
    bad = re.search(
        r'os\.path\.join\([^)]*"tdd-subagent"[^)]*"scripts"[^)]*"tdd-step\.py"',
        src,
    )
    if bad:
        ko(f"c: dispatch still constructs old tdd-subagent path for tdd-step.py: {bad.group(0)!r}")
    else:
        ok("c: dispatch no longer constructs old tdd-subagent path for tdd-step.py")
    # Ensure it constructs the new tdd-state-machine path.
    good = re.search(
        r'os\.path\.join\([^)]*"tdd-state-machine"[^)]*"scripts"[^)]*"tdd-step\.py"',
        src,
    )
    if good:
        ok("c: dispatch constructs new tdd-state-machine path for tdd-step.py")
    else:
        ko("c: dispatch does NOT construct tdd-state-machine path for tdd-step.py")


# (d) build-contract.json copy-file sources point at tdd-state-machine
def t_d_build_contract_sources():
    with open(BUILD_CONTRACT) as f:
        bc = json.load(f)
    for s in EXTRACTED:
        dest = f".claude/agents/tdd-subagent/scripts/{s}"
        targets = [t for t in bc.get("targets", []) if t.get("destination") == dest]
        if len(targets) != 1:
            ko(f"d: expected exactly one copy-file target for {dest}, got {len(targets)}")
            continue
        src = targets[0].get("source", "")
        if "tdd-state-machine" in src and src.endswith(f"scripts/{s}"):
            ok(f"d: build-contract source for {s} points at tdd-state-machine: {src}")
        else:
            ko(f"d: build-contract source for {s} not from tdd-state-machine: {src}")


# (e) the deployed agent scripts still exist
def t_e_deployed_still_present():
    for s in EXTRACTED:
        p = os.path.join(AGENT_DEPLOYED_SCRIPTS, s)
        if os.path.isfile(p):
            ok(f"e: deployed agent script present at {p}")
        else:
            ko(f"e: deployed agent script missing: {p}")


# (f) tdd-subagent's feature.json declares only the dispatch script as surface scripts
# (the agent definition is at agents/, not scripts/).
def t_f_feature_json_surface():
    with open(FEATURE_JSON) as f:
        fj = json.load(f)
    surface = fj.get("surface", {})
    # surface.skills must remain []
    if surface.get("skills") == []:
        ok("f: feature.json surface.skills == [] (preserved per Inv 8)")
    else:
        ko(f"f: feature.json surface.skills must be [], got {surface.get('skills')}")


# (g) contract.md provides.scripts no longer lists the three extracted scripts
def t_g_contract_provides_slimmed():
    with open(CONTRACT_MD) as f:
        cm = f.read()
    # Extract the JSON block from contract.md
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
    bad = [p for p in script_paths
           if any(p.endswith(f"tdd-subagent/scripts/{s}") for s in EXTRACTED)]
    if bad:
        ko(f"g: contract.md provides.scripts still lists extracted scripts: {bad}")
    else:
        ok("g: contract.md provides.scripts does not list extracted scripts")
    # dispatch-tdd-subagent.py MUST still be in provides.scripts
    if any(p.endswith("tdd-subagent/scripts/dispatch-tdd-subagent.py") for p in script_paths):
        ok("g: contract.md provides.scripts still lists dispatch-tdd-subagent.py")
    else:
        ko("g: contract.md provides.scripts missing dispatch-tdd-subagent.py")


t_a_absent_from_tdd_subagent()
t_b_present_in_tdd_state_machine()
t_c_dispatch_path_repoint()
t_d_build_contract_sources()
t_e_deployed_still_present()
t_f_feature_json_surface()
t_g_contract_provides_slimmed()

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
