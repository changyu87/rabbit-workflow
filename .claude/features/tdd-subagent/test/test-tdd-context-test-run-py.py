#!/usr/bin/env python3
# E2E test for tdd-subagent Inv 22 (BUG-17, was Inv 29 in v1.19.0 before
# BACKLOG-12 renumber): tdd-context.py guidance text MUST reference
# `test/run.py` (Python runner) not stale `test/run.sh`.
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
CTX = os.path.join(FEATURE_DIR, 'scripts', 'tdd-context.py')
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


# c1: source does not contain stale `test/run.sh`
def c1():
    with open(CTX) as f:
        src = f.read()
    if 'test/run.sh' in src:
        ko('c1: stale `test/run.sh` reference still present in tdd-context.py')
    else:
        ok('c1: no stale `test/run.sh` reference in source')


# c2: source contains `test/run.py`
def c2():
    with open(CTX) as f:
        src = f.read()
    if 'test/run.py' in src:
        ok('c2: `test/run.py` reference present in source')
    else:
        ko('c2: `test/run.py` reference missing from source')


# c3: runtime impl-state guidance string mentions test/run.py, not test/run.sh
def c3():
    d = os.path.join(TMPROOT, 'c3')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        json.dump({
            "name": "c3",
            "tdd_state": "impl",
            "deprecation_criterion": "x",
        }, f)
    proc = subprocess.run(['python3', CTX, d], capture_output=True, text=True)
    if proc.returncode != 0:
        ko(f"c3: rc={proc.returncode} err={proc.stderr}")
        return
    guidance = json.loads(proc.stdout).get('guidance', '')
    if 'test/run.sh' in guidance:
        ko(f"c3: impl guidance still references test/run.sh: {guidance!r}")
        return
    if 'test/run.py' in guidance:
        ok('c3: impl guidance references test/run.py')
    else:
        ko(f"c3: impl guidance does not reference test/run.py: {guidance!r}")


print(f"running tdd-context test/run.py reference tests against {CTX}")
c1(); c2(); c3()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
