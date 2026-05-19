#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BUG-53:
#   1. tdd-context.py _ALLOWED_NEXT['test-green'] must include 'spec-update'
#      so the cycle-restart path surfaces to subagents (parity with
#      tdd-step.py _FORWARD_ALT per BUG-51 fix).
#   2. tdd-context.py guidance for test-green must mention the cycle-restart
#      option (spec-update), not only the PR/merge path.
#   3. contract.md provides.scripts[] entry for tdd-step.py must describe
#      the current stdout format ('[\xf0\x9f\x90\x87 rabbit \xf0\x9f\x90\x87]'
#      brand with FROM_STATE -> TO_STATE) per Inv 5.
#   4. contract.md reads.files must not list the dead
#      `.claude/backlogs/<feature-name>/` directory (removed post-rabbit-file
#      unification).
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
CTX = os.path.join(FEATURE_DIR, 'scripts', 'tdd-context.py')
CONTRACT_MD = os.path.join(FEATURE_DIR, 'docs', 'spec', 'contract.md')
TMPROOT = tempfile.mkdtemp()

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def make_feat(name, tdd_state):
    d = os.path.join(TMPROOT, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        json.dump({
            "name": name,
            "tdd_state": tdd_state,
            "deprecation_criterion": "x",
        }, f)
    return d


def run_ctx(d):
    proc = subprocess.run(['python3', CTX, d], capture_output=True, text=True)
    if proc.returncode != 0:
        return None, proc.stderr
    return json.loads(proc.stdout), None


# c1: allowed_next_states for test-green includes 'spec-update'
def c1():
    d = make_feat('c1', 'test-green')
    data, err = run_ctx(d)
    if data is None:
        ko(f"c1: ctx failed: {err}")
        return
    nxt = data.get('allowed_next_states', [])
    if 'spec-update' in nxt:
        ok(f"c1: test-green allows spec-update (got {nxt})")
    else:
        ko(f"c1: test-green missing spec-update in allowed_next_states: {nxt}")


# c2: allowed_next_states for test-green still includes 'deprecated'
def c2():
    d = make_feat('c2', 'test-green')
    data, err = run_ctx(d)
    if data is None:
        ko(f"c2: ctx failed: {err}")
        return
    nxt = data.get('allowed_next_states', [])
    if 'deprecated' in nxt:
        ok(f"c2: test-green still allows deprecated (got {nxt})")
    else:
        ko(f"c2: test-green missing deprecated in allowed_next_states: {nxt}")


# c3: test-green guidance text mentions the cycle-restart / spec-update path
def c3():
    d = make_feat('c3', 'test-green')
    data, err = run_ctx(d)
    if data is None:
        ko(f"c3: ctx failed: {err}")
        return
    guidance = data.get('guidance', '')
    # Accept either explicit 'spec-update' or 'cycle' wording for restart.
    if 'spec-update' in guidance or 'cycle' in guidance.lower():
        ok(f"c3: test-green guidance mentions cycle-restart path")
    else:
        ko(f"c3: test-green guidance does not mention cycle-restart: {guidance!r}")


# c4: contract.md describes the current emoji brand stdout format for tdd-step.py
def c4():
    with open(CONTRACT_MD) as f:
        src = f.read()
    if '\U0001f407 rabbit \U0001f407' in src:
        ok('c4: contract.md uses emoji brand stdout format')
    else:
        ko('c4: contract.md missing emoji brand stdout format for tdd-step.py')


# c5: contract.md no longer lists the stale '[rabbit] ━━━' format
def c5():
    with open(CONTRACT_MD) as f:
        src = f.read()
    # The stale prose explicitly wrote "[rabbit] ━━━". The current format
    # uses the emoji brand and FROM_STATE -> TO_STATE ordering.
    if "'[rabbit] ━━━" in src or '"[rabbit] ━━━' in src:
        ko("c5: contract.md still references stale '[rabbit] ━━━' format")
    else:
        ok("c5: contract.md no longer references stale '[rabbit] ━━━' format")


# c6: contract.md reads.files no longer lists the dead .claude/backlogs/ entry
def c6():
    with open(CONTRACT_MD) as f:
        src = f.read()
    if '.claude/backlogs/' in src:
        ko("c6: contract.md still references dead .claude/backlogs/ reads entry")
    else:
        ok("c6: contract.md no longer references dead .claude/backlogs/ entry")


print(f"running BUG-53 drift fix tests against {CTX} and {CONTRACT_MD}")
c1(); c2(); c3(); c4(); c5(); c6()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
