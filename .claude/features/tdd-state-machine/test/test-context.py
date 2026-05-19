#!/usr/bin/env python3
# End-to-end test of tdd-context.py: emits machine-first JSON describing the
# feature's current TDD state for subagent prompts.
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


def fix(d, n, s):
    # BACKLOG-10: thin wrapper around shared test_helpers.make_feature_dir
    # so the canonical flat-schema feature.json shape lives in ONE place.
    _make_feature_dir(d, n, s)


def run(*args):
    stdout_f = os.path.join(TMPROOT, 'stdout')
    stderr_f = os.path.join(TMPROOT, 'stderr')
    with open(stdout_f, 'w') as out, open(stderr_f, 'w') as err:
        result = subprocess.run(['python3', CTX] + list(args), stdout=out, stderr=err)
    return result.returncode


def read_out():
    with open(os.path.join(TMPROOT, 'stdout')) as f:
        return f.read()


# c1: emits valid JSON with required fields
def c1():
    d = os.path.join(TMPROOT, 'c1')
    fix(d, 'c1', 'impl')
    rc = run(d)
    if rc != 0:
        ko(f"c1: rc={rc}")
        return
    out = read_out()
    try:
        data = json.loads(out)
    except Exception:
        ko(f"c1: not valid JSON: {out}")
        return
    fname = data.get('feature_name', '')
    cs = data.get('current_state', '')
    ans_type = type(data.get('allowed_next_states')).__name__
    guide = data.get('guidance', '')
    if fname == 'c1' and cs == 'impl' and ans_type == 'list' and guide:
        ok('c1: JSON has feature_name, current_state, allowed_next_states[], guidance')
    else:
        ko(f"c1: fname={fname} cs={cs} ans={ans_type} guide_len={len(guide)}")


# c2: --text flag emits human-readable view (non-JSON)
def c2():
    d = os.path.join(TMPROOT, 'c2')
    fix(d, 'c2', 'spec')
    rc = run('--text', d)
    if rc != 0:
        ko(f"c2: rc={rc}")
        return
    out = read_out()
    try:
        json.loads(out)
        ko('c2: --text should NOT be JSON')
        return
    except Exception:
        pass
    if 'spec' in out.lower() and 'next' in out.lower():
        ok('c2: --text emits human view with state and next')
    else:
        ko(f"c2: missing keywords; out={out}")


# c3: guidance differs by state
def c3():
    d1 = os.path.join(TMPROOT, 'c3a')
    fix(d1, 'c3a', 'test-red')
    d2 = os.path.join(TMPROOT, 'c3b')
    fix(d2, 'c3b', 'spec-update')
    run(d1)
    out1 = read_out()
    run(d2)
    out2 = read_out()
    try:
        g1 = json.loads(out1).get('guidance', '')
        g2 = json.loads(out2).get('guidance', '')
    except Exception:
        ko(f"c3: parse error")
        return
    if g1 and g2 and g1 != g2:
        ok('c3: guidance differs by state')
    else:
        ko(f"c3: g1='{g1}' g2='{g2}'")


# c4: includes the deprecation criterion
def c4():
    d = os.path.join(TMPROOT, 'c4')
    fix(d, 'c4', 'impl')
    run(d)
    out = read_out()
    try:
        crit = json.loads(out).get('deprecation_criterion', '')
    except Exception:
        ko('c4: parse error')
        return
    if crit == 'fixture':
        ok('c4: deprecation_criterion surfaced')
    else:
        ko(f"c4: crit='{crit}'")


# c5: legacy nested 'contract' object is passed through when present.
# Per spec Inv 25 (post-BACKLOG-12 renumber; was Inv 33 in v1.18.x and
# Inv 29 in v1.19.0), the flat shape is canonical and has no nested 'contract'
# field; this test explicitly exercises the legacy nested form as a
# backward-compatibility guard for any feature.json that still carries it.
def c5():
    d = os.path.join(TMPROOT, 'c5')
    os.makedirs(os.path.join(d, 'test'), exist_ok=True)
    feature_json = {
        "name": "c5",
        "version": "0.1.0",
        "owner": "test",
        "tdd_state": "impl",
        "summary": "legacy fixture",
        "surface": {},
        "deprecation_criterion": "fixture",
        # Legacy nested contract object — backward-compat only.
        "contract": {"reads": [], "writes": [], "invokes": []},
    }
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        json.dump(feature_json, f, indent=2)
    with open(os.path.join(d, 'spec.md'), 'w') as f:
        f.write('\n')
    with open(os.path.join(d, 'contract.md'), 'w') as f:
        f.write('\n')
    run_py = os.path.join(d, 'test', 'run.py')
    with open(run_py, 'w') as f:
        f.write('#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n')
    os.chmod(run_py, 0o755)
    run(d)
    out = read_out()
    try:
        data = json.loads(out)
        if isinstance(data.get('contract', {}).get('reads'), list):
            ok('c5: legacy nested contract object passed through (backward-compat)')
        else:
            ko('c5: legacy contract.reads missing in output')
    except Exception:
        ko(f"c5: parse error; out={out}")


print(f"running tdd-context tests against {CTX}")
c1(); c2(); c3(); c4(); c5()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
