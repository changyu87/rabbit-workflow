#!/usr/bin/env python3
# End-to-end test of tdd-drift-check.py.
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
DRIFT = os.path.join(FEATURE_DIR, 'scripts', 'tdd-drift-check.py')
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


def fix(d, n, s, rc_code):
    # BACKLOG-10: thin wrapper around shared test_helpers.make_feature_dir
    # so the canonical flat-schema feature.json shape lives in ONE place.
    _make_feature_dir(d, n, s, run_exit=rc_code)


def run(*args):
    stdout_f = os.path.join(TMPROOT, 'stdout')
    stderr_f = os.path.join(TMPROOT, 'stderr')
    with open(stdout_f, 'w') as out, open(stderr_f, 'w') as err:
        result = subprocess.run(['python3', DRIFT] + list(args), stdout=out, stderr=err)
    return result.returncode


def read_err():
    with open(os.path.join(TMPROOT, 'stderr')) as f:
        return f.read().strip()


# d1: test-green claim + tests pass -> ok
def d1():
    d = os.path.join(TMPROOT, 'd1')
    fix(d, 'd1', 'test-green', 0)
    rc = run(d)
    if rc == 0:
        ok('d1: test-green + passing tests -> ok')
    else:
        ko(f"d1: rc={rc} stderr={read_err()}")


# d2: test-green claim + tests fail -> drift detected
def d2():
    d = os.path.join(TMPROOT, 'd2')
    fix(d, 'd2', 'test-green', 1)
    rc = run(d)
    if rc != 0:
        ok('d2: test-green + failing tests -> drift detected')
    else:
        ko(f"d2: rc={rc}")


# d3: test-red claim + tests fail -> ok (red is the expected state)
def d3():
    d = os.path.join(TMPROOT, 'd3')
    fix(d, 'd3', 'test-red', 1)
    rc = run(d)
    if rc == 0:
        ok('d3: test-red + failing tests -> ok')
    else:
        ko(f"d3: rc={rc} stderr={read_err()}")


# d4: test-red claim + tests pass -> drift (suspicious; tests should be red)
def d4():
    d = os.path.join(TMPROOT, 'd4')
    fix(d, 'd4', 'test-red', 0)
    rc = run(d)
    if rc != 0:
        ok('d4: test-red + passing tests -> drift')
    else:
        ko(f"d4: rc={rc}")


# d5: spec state -> not checked against tests (no claim about test outcome)
def d5():
    d = os.path.join(TMPROOT, 'd5')
    fix(d, 'd5', 'spec', 1)
    rc = run(d)
    if rc == 0:
        ok('d5: spec state -> ok regardless of tests')
    else:
        ko(f"d5: rc={rc}")


# d6: impl state is transitional - tests may pass or fail; both ok
def d6():
    d1p = os.path.join(TMPROOT, 'd6a')
    fix(d1p, 'd6a', 'impl', 0)
    d2p = os.path.join(TMPROOT, 'd6b')
    fix(d2p, 'd6b', 'impl', 1)
    rc1 = run(d1p)
    rc2 = run(d2p)
    if rc1 == 0 and rc2 == 0:
        ok('d6: impl state -> ok regardless of test outcome')
    else:
        ko(f"d6: rc1={rc1} rc2={rc2}")


# d7: spec-update state -> not checked against tests
def d7():
    d = os.path.join(TMPROOT, 'd7')
    fix(d, 'd7', 'spec-update', 1)
    rc = run(d)
    if rc == 0:
        ok('d7: spec-update state -> ok regardless of tests')
    else:
        ko(f"d7: rc={rc}")


# d8: deprecated state -> not checked against tests
def d8():
    d = os.path.join(TMPROOT, 'd8')
    fix(d, 'd8', 'deprecated', 1)
    rc = run(d)
    if rc == 0:
        ok('d8: deprecated state -> ok regardless of tests')
    else:
        ko(f"d8: rc={rc}")


print(f"running drift-check tests against {DRIFT}")
d1(); d2(); d3(); d4(); d5(); d6(); d7(); d8()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
