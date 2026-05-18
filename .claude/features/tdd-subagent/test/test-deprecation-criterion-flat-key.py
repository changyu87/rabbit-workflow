#!/usr/bin/env python3
# E2E test for Inv 28 (BUG-16): tdd-context.py MUST read flat
# `deprecation_criterion` from feature.json, with fallback to nested
# `deprecation.criterion` for backward compat. Flat wins when both are
# present.
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


def write_feature(d, payload):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        json.dump(payload, f, indent=2)


def run_ctx(d):
    proc = subprocess.run(['python3', CTX, d], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


# c1: flat deprecation_criterion is read
def c1():
    d = os.path.join(TMPROOT, 'c1')
    write_feature(d, {
        "name": "c1",
        "tdd_state": "impl",
        "deprecation_criterion": "FLAT-VALUE",
    })
    rc, out, err = run_ctx(d)
    if rc != 0:
        ko(f"c1: rc={rc} err={err}")
        return
    crit = json.loads(out).get('deprecation_criterion', '')
    if crit == 'FLAT-VALUE':
        ok('c1: flat deprecation_criterion read')
    else:
        ko(f"c1: got crit={crit!r}")


# c2: nested deprecation.criterion is fallback when flat is absent
def c2():
    d = os.path.join(TMPROOT, 'c2')
    write_feature(d, {
        "name": "c2",
        "tdd_state": "impl",
        "deprecation": {"criterion": "NESTED-LEGACY"},
    })
    rc, out, err = run_ctx(d)
    if rc != 0:
        ko(f"c2: rc={rc} err={err}")
        return
    crit = json.loads(out).get('deprecation_criterion', '')
    if crit == 'NESTED-LEGACY':
        ok('c2: nested deprecation.criterion fallback')
    else:
        ko(f"c2: got crit={crit!r}")


# c3: flat wins when both are present
def c3():
    d = os.path.join(TMPROOT, 'c3')
    write_feature(d, {
        "name": "c3",
        "tdd_state": "impl",
        "deprecation_criterion": "FLAT-WINS",
        "deprecation": {"criterion": "NESTED-LOSES"},
    })
    rc, out, err = run_ctx(d)
    if rc != 0:
        ko(f"c3: rc={rc} err={err}")
        return
    crit = json.loads(out).get('deprecation_criterion', '')
    if crit == 'FLAT-WINS':
        ok('c3: flat key wins over nested')
    else:
        ko(f"c3: got crit={crit!r}")


# c4: real tdd-subagent feature.json uses flat key and surfaces correctly
def c4():
    real_dir = FEATURE_DIR
    rc, out, err = run_ctx(real_dir)
    if rc != 0:
        ko(f"c4: rc={rc} err={err}")
        return
    crit = json.loads(out).get('deprecation_criterion', '')
    # The real tdd-subagent/feature.json now uses flat key. Crit should not be empty.
    if crit and 'rabbit' in crit.lower():
        ok('c4: real feature.json flat key surfaces non-empty criterion')
    else:
        ko(f"c4: empty/unexpected crit={crit!r}")


print(f"running deprecation_criterion flat-key tests against {CTX}")
c1(); c2(); c3(); c4()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
