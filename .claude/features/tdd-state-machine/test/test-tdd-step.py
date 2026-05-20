#!/usr/bin/env python3
# End-to-end test of tdd-step.py: show, next, transitions, transition, --force.
import json
import os
import re
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


def fix(d, n, s):
    # BACKLOG-10: thin wrapper around shared test_helpers.make_feature_dir
    # so the canonical flat-schema feature.json shape lives in ONE place.
    _make_feature_dir(d, n, s)


def run(*args):
    stdout_f = os.path.join(TMPROOT, 'stdout')
    stderr_f = os.path.join(TMPROOT, 'stderr')
    with open(stdout_f, 'wb') as out, open(stderr_f, 'wb') as err:
        result = subprocess.run(['python3', TDD_STEP] + list(args), stdout=out, stderr=err)
    return result.returncode


def read_out():
    with open(os.path.join(TMPROOT, 'stdout')) as f:
        return f.read().strip()


def read_err():
    with open(os.path.join(TMPROOT, 'stderr')) as f:
        return f.read().strip()


# t1: show returns current state
def t1():
    d = os.path.join(TMPROOT, 't1')
    fix(d, 't1', 'spec')
    rc = run('show', d)
    out = read_out()
    if rc == 0 and out == 'spec':
        ok('t1: show returns spec')
    else:
        ko(f"t1: rc={rc} out='{out}'")


# t2: next returns expected next state
def t2():
    d = os.path.join(TMPROOT, 't2')
    fix(d, 't2', 'spec')
    rc = run('next', d)
    out = read_out()
    if rc == 0 and out == 'spec-update':
        ok('t2: next from spec is spec-update')
    else:
        ko(f"t2: rc={rc} out='{out}'")


# t3: transition to next-allowed succeeds and writes file
def t3():
    d = os.path.join(TMPROOT, 't3')
    fix(d, 't3', 'spec')
    rc = run('transition', d, 'spec-update')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'spec-update':
        ok('t3: spec -> spec-update succeeds')
    else:
        ko(f"t3: rc={rc} newstate={newstate} stderr={read_err()}")


# t4: skip transition denied (spec -> test-green)
def t4():
    d = os.path.join(TMPROOT, 't4')
    fix(d, 't4', 'spec')
    rc = run('transition', d, 'test-green')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'spec':
        ok('t4: spec -> test-green denied (skip)')
    else:
        ko(f"t4: rc={rc} newstate={newstate} stderr={read_err()}")


# t5: backward transition denied without --force (impl -> test-red)
def t5():
    d = os.path.join(TMPROOT, 't5')
    fix(d, 't5', 'impl')
    rc = run('transition', d, 'test-red')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'impl':
        ok('t5: impl -> test-red denied without --force')
    else:
        ko(f"t5: rc={rc} newstate={newstate} stderr={read_err()}")


# t6: backward transition with --force succeeds
def t6():
    d = os.path.join(TMPROOT, 't6')
    fix(d, 't6', 'impl')
    rc = run('transition', d, 'test-red', '--force')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'test-red':
        ok('t6: impl -> test-red allowed with --force')
    else:
        ko(f"t6: rc={rc} newstate={newstate} stderr={read_err()}")


# t7: transition updates the 'updated' field
def t7():
    d = os.path.join(TMPROOT, 't7')
    fix(d, 't7', 'spec')
    fj = os.path.join(d, 'feature.json')
    with open(fj) as f:
        data = json.load(f)
    data['updated'] = '1999-01-01'
    with open(fj, 'w') as f:
        json.dump(data, f)
    run('transition', d, 'spec-update')
    with open(fj) as f:
        upd = json.load(f)['updated']
    if upd != '1999-01-01' and re.match(r'^\d{4}-\d{2}-\d{2}$', upd):
        ok(f"t7: 'updated' field refreshed to {upd}")
    else:
        ko(f"t7: updated={upd}")


# t8: terminal state - deprecated cannot transition
def t8():
    d = os.path.join(TMPROOT, 't8')
    fix(d, 't8', 'deprecated')
    rc = run('transition', d, 'spec', '--force')
    if rc != 0:
        ok('t8: deprecated is terminal (no forward transitions allowed, even with --force)')
    else:
        ko(f"t8: rc={rc} - deprecated must reject all transitions (terminal state)")


# t9: full forward path works end-to-end
def t9():
    d = os.path.join(TMPROOT, 't9')
    fix(d, 't9', 'spec')
    good = True
    if run('transition', d, 'spec-update') != 0:
        good = False
    if good and run('transition', d, 'test-red', '--spec-no-change-reason', 't9 full-path fixture') != 0:
        good = False
    for nxt in ['impl', 'test-green', 'deprecated']:
        if good and run('transition', d, nxt) != 0:
            good = False
            break
    with open(os.path.join(d, 'feature.json')) as f:
        final = json.load(f)['tdd_state']
    if good and final == 'deprecated':
        ok('t9: full forward path spec -> deprecated')
    else:
        ko(f"t9: ok={good} final={final}")


# t10: invalid target state denied
def t10():
    d = os.path.join(TMPROOT, 't10')
    fix(d, 't10', 'spec')
    rc = run('transition', d, 'bogus')
    if rc != 0:
        ok('t10: invalid target state denied')
    else:
        ko(f"t10: rc={rc}")


# t11: transitions sub-command lists allowed next states (forward without --force)
def t11():
    d = os.path.join(TMPROOT, 't11')
    fix(d, 't11', 'test-green')
    rc = run('transitions', d)
    out = read_out()
    if rc == 0 and 'deprecated' in out:
        ok('t11: transitions from test-green includes deprecated')
    else:
        ko(f"t11: rc={rc} out='{out}'")


# t_su1: spec-update is a valid state (--force into spec-update must succeed)
def t_su1():
    d = os.path.join(TMPROOT, 'tsu1')
    fix(d, 'tsu1', 'spec')
    rc = run('transition', d, 'spec-update', '--force')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'spec-update':
        ok('tsu1: spec-update is a valid state (--force accepted)')
    else:
        ko(f"tsu1: rc={rc} newstate={newstate} stderr={read_err()}")


# t_su2: spec → spec-update is the forward transition from spec
def t_su2():
    d = os.path.join(TMPROOT, 'tsu2')
    fix(d, 'tsu2', 'spec')
    rc = run('transition', d, 'spec-update')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'spec-update':
        ok('tsu2: spec -> spec-update forward transition succeeds')
    else:
        ko(f"tsu2: rc={rc} newstate={newstate} stderr={read_err()}")


# t_su3: spec-update → test-red allowed when --spec-no-change-reason provided
def t_su3():
    d = os.path.join(TMPROOT, 'tsu3')
    fix(d, 'tsu3', 'spec-update')
    rc = run('transition', d, 'test-red', '--spec-no-change-reason', 'bug fix; spec already correct')
    with open(os.path.join(d, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'test-red':
        ok('tsu3: spec-update -> test-red with --spec-no-change-reason succeeds')
    else:
        ko(f"tsu3: rc={rc} newstate={newstate} stderr={read_err()}")


# t_su4: spec-update → test-red blocked when spec unmodified and no reason given
def t_su4():
    d = os.path.join(TMPROOT, 'tsu4_repo')
    subprocess.run(['git', 'init', d], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.email', 'test@test.com'], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.name', 'Test'], capture_output=True)
    feat = os.path.join(d, 'feat')
    fix(feat, 'tsu4', 'spec-update')
    os.makedirs(os.path.join(feat, 'docs', 'spec'), exist_ok=True)
    with open(os.path.join(feat, 'docs', 'spec', 'spec.md'), 'w') as f:
        f.write('spec content')
    subprocess.run(['git', '-C', d, 'add', '-A'], capture_output=True)
    subprocess.run(['git', '-C', d, 'commit', '-m', 'init'], capture_output=True)
    # spec.md NOT modified after commit -> gate must block
    stdout_f = os.path.join(TMPROOT, 'stdout_tsu4')
    stderr_f = os.path.join(TMPROOT, 'err_tsu4')
    with open(stdout_f, 'wb') as out, open(stderr_f, 'wb') as err:
        result = subprocess.run(
            ['python3', TDD_STEP, 'transition', feat, 'test-red'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': d}
        )
    rc = result.returncode
    with open(os.path.join(feat, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'spec-update':
        ok('tsu4: spec-update -> test-red blocked when spec unmodified and no reason')
    else:
        with open(stderr_f) as f:
            err_txt = f.read()
        ko(f"tsu4: rc={rc} newstate={newstate} stderr={err_txt}")


# t_su5: spec-update → test-red allowed when spec.md modified (git diff detects change)
def t_su5():
    d = os.path.join(TMPROOT, 'tsu5_repo')
    subprocess.run(['git', 'init', d], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.email', 'test@test.com'], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.name', 'Test'], capture_output=True)
    feat = os.path.join(d, 'feat')
    fix(feat, 'tsu5', 'spec-update')
    os.makedirs(os.path.join(feat, 'docs', 'spec'), exist_ok=True)
    with open(os.path.join(feat, 'docs', 'spec', 'spec.md'), 'w') as f:
        f.write('original spec')
    subprocess.run(['git', '-C', d, 'add', '-A'], capture_output=True)
    subprocess.run(['git', '-C', d, 'commit', '-m', 'init'], capture_output=True)
    # Modify spec.md -> git diff will show changes -> gate must allow
    with open(os.path.join(feat, 'docs', 'spec', 'spec.md'), 'a') as f:
        f.write('\nupdated spec')
    stdout_f = os.path.join(TMPROOT, 'stdout_tsu5')
    stderr_f = os.path.join(TMPROOT, 'err_tsu5')
    with open(stdout_f, 'wb') as out, open(stderr_f, 'wb') as err:
        result = subprocess.run(
            ['python3', TDD_STEP, 'transition', feat, 'test-red'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': d}
        )
    rc = result.returncode
    with open(os.path.join(feat, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'test-red':
        ok('tsu5: spec-update -> test-red allowed when spec.md modified in git')
    else:
        with open(stderr_f) as f:
            err_txt = f.read()
        ko(f"tsu5: rc={rc} newstate={newstate} stderr={err_txt}")


# t_su6: next from spec-update is test-red
def t_su6():
    d = os.path.join(TMPROOT, 'tsu6')
    fix(d, 'tsu6', 'spec-update')
    rc = run('next', d)
    out = read_out()
    if rc == 0 and out == 'test-red':
        ok('tsu6: next from spec-update is test-red')
    else:
        ko(f"tsu6: rc={rc} out='{out}'")


# t_rbt1: tdd-step.py transition stdout contains the centralized brand
# `[🐇 rabbit 🐇]` (post-BACKLOG-11; renderer is rabbit_print).
def t_rbt1():
    d = os.path.join(TMPROOT, 't_rbt1')
    fix(d, 't_rbt1', 'spec')
    run('transition', d, 'spec-update')
    out = read_out()
    if '[\U0001f407 rabbit \U0001f407]' in out:
        ok('t_rbt1: transition stdout contains [🐇 rabbit 🐇] brand')
    else:
        ko(f"t_rbt1: brand not found in stdout: '{out}'")


# t_rbt2: tdd-step.py transition stdout contains ANSI green code
def t_rbt2():
    d = os.path.join(TMPROOT, 't_rbt2')
    fix(d, 't_rbt2', 'spec')
    run('transition', d, 'spec-update')
    with open(os.path.join(TMPROOT, 'stdout'), 'rb') as f:
        out_bytes = f.read()
    if b'\x1b[32m' in out_bytes:
        ok('t_rbt2: transition stdout contains ANSI green (\\x1b[32m)')
    else:
        ko('t_rbt2: ANSI green not found in stdout')


# t_rbt3: tdd-step.py transition --force stderr contains ANSI red code
def t_rbt3():
    d = os.path.join(TMPROOT, 't_rbt3')
    fix(d, 't_rbt3', 'impl')
    run('transition', d, 'test-red', '--force')
    with open(os.path.join(TMPROOT, 'stderr'), 'rb') as f:
        err_bytes = f.read()
    if b'\x1b[31m' in err_bytes:
        ok('t_rbt3: forced transition stderr contains ANSI red (\\x1b[31m)')
    else:
        ko(f"t_rbt3: ANSI red not found in stderr")


# t_ref1: _run_enforcement_checks is defined as a function in tdd-step.py
def t_ref1():
    with open(TDD_STEP) as f:
        content = f.read()
    if re.search(r'^def _run_enforcement_checks\(', content, re.MULTILINE):
        ok('t_ref1: _run_enforcement_checks function is defined in tdd-step.py')
    else:
        ko('t_ref1: _run_enforcement_checks function NOT found in tdd-step.py')


# t_ref2: enforcement check block appears only once (no copy-paste duplication)
def t_ref2():
    with open(TDD_STEP) as f:
        content = f.read()
    count = content.count('check-tests-non-interactive.py')
    if count == 1:
        ok(f"t_ref2: enforcement check block appears exactly once (count={count})")
    else:
        ko(f"t_ref2: enforcement check block appears {count} times (expected 1 — deduplication required)")


print(f"running tdd-step tests against {TDD_STEP}")
t1(); t2(); t3(); t4(); t5(); t6(); t7(); t8(); t9(); t10(); t11()
t_su1(); t_su2(); t_su3(); t_su4(); t_su5(); t_su6()
t_rbt1(); t_rbt2(); t_rbt3()
t_ref1(); t_ref2()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
