#!/usr/bin/env python3
# test-forward-alt-test-green-to-spec-update.py — Inv 4 regression test.
#
# Inv 4: tdd-step.py's _FORWARD_ALT MUST include test-green -> spec-update.
# This test exercises the path end-to-end: from a test-green fixture,
# `tdd-step.py transition <feat> spec-update` exits 0 and feature.json now
# reads "spec-update".
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')
TMPROOT = tempfile.mkdtemp()

sys.path.insert(0, SCRIPT_DIR)
from test_helpers import make_feature_dir as _make_feature_dir  # noqa: E402

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


def run(*args):
    return subprocess.run(
        ['python3', TDD_STEP] + list(args),
        capture_output=True, text=True,
    )


# fa1: test-green -> spec-update is a valid forward transition (no --force).
def fa1():
    d = os.path.join(TMPROOT, 'fa1')
    _make_feature_dir(d, 'fa1', 'test-green')
    res = run('transition', d, 'spec-update')
    if res.returncode != 0:
        ko(f"fa1: rc={res.returncode} stderr={res.stderr.strip()}")
        return
    with open(os.path.join(d, 'feature.json')) as f:
        data = json.load(f)
    if data.get('tdd_state') == 'spec-update':
        ok('fa1: test-green -> spec-update accepted; feature.json updated')
    else:
        ko(f"fa1: feature.json tdd_state='{data.get('tdd_state')}' (expected spec-update)")


# fa2: `transitions` lists spec-update among the forward targets from test-green.
def fa2():
    d = os.path.join(TMPROOT, 'fa2')
    _make_feature_dir(d, 'fa2', 'test-green')
    res = run('transitions', d)
    if res.returncode != 0:
        ko(f"fa2: rc={res.returncode} stderr={res.stderr.strip()}")
        return
    targets = res.stdout.strip().split()
    if 'spec-update' in targets:
        ok(f"fa2: transitions includes spec-update (got: {targets})")
    else:
        ko(f"fa2: transitions missing spec-update (got: {targets})")


print(f"running forward-alt tests against {TDD_STEP}")
fa1(); fa2()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
