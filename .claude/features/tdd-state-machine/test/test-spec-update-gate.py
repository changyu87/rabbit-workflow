#!/usr/bin/env python3
# test-spec-update-gate.py — Inv 8 coverage.
#
# Inv 8: spec-update -> test-red requires either
#   (a) non-empty git diff under <feature-dir>/docs/spec/, OR
#   (b) --spec-no-change-reason <non-empty-reason>.
# When neither holds, the transition is denied with exit 1.
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


def _run(cmd, env=None):
    res = subprocess.run(cmd, capture_output=True, env=env)
    return res.returncode, res.stdout, res.stderr


# Inv 8(b): --spec-no-change-reason satisfies the gate.
def t_reason_allows():
    d = os.path.join(TMPROOT, 't_reason')
    _make_feature_dir(d, 't_reason', 'spec-update')
    rc, _, err = _run(
        ['python3', TDD_STEP, 'transition', d, 'test-red',
         '--spec-no-change-reason', 'bug fix; spec already correct']
    )
    with open(os.path.join(d, 'feature.json')) as f:
        data = json.load(f)
    if rc == 0 and data['tdd_state'] == 'test-red':
        ok('Inv 8: --spec-no-change-reason satisfies gate')
    else:
        ko(f"reason: rc={rc} state={data['tdd_state']} stderr={err!r}")


# Inv 8: reason is persisted on feature.json.
def t_reason_persisted():
    d = os.path.join(TMPROOT, 't_reason_persist')
    _make_feature_dir(d, 't_reason_persist', 'spec-update')
    _run(
        ['python3', TDD_STEP, 'transition', d, 'test-red',
         '--spec-no-change-reason', 'persisted reason text']
    )
    with open(os.path.join(d, 'feature.json')) as f:
        data = json.load(f)
    if data.get('spec_no_change_reason') == 'persisted reason text':
        ok('Inv 8: spec_no_change_reason persisted on feature.json')
    else:
        ko(f"persist: {data.get('spec_no_change_reason')!r}")


# Inv 8: --spec-no-change-reason without a value -> exit 2.
def t_reason_missing_value():
    d = os.path.join(TMPROOT, 't_reason_missing')
    _make_feature_dir(d, 't_reason_missing', 'spec-update')
    rc, _, err = _run(
        ['python3', TDD_STEP, 'transition', d, 'test-red', '--spec-no-change-reason']
    )
    if rc == 2 and b'requires a non-empty reason' in err:
        ok('Inv 8: --spec-no-change-reason missing value -> exit 2')
    else:
        ko(f"missing: rc={rc} stderr={err!r}")


# Inv 8: --spec-no-change-reason with empty string -> exit 2.
def t_reason_empty():
    d = os.path.join(TMPROOT, 't_reason_empty')
    _make_feature_dir(d, 't_reason_empty', 'spec-update')
    rc, _, err = _run(
        ['python3', TDD_STEP, 'transition', d, 'test-red', '--spec-no-change-reason', '']
    )
    if rc == 2 and b'requires a non-empty reason' in err:
        ok('Inv 8: --spec-no-change-reason empty value -> exit 2')
    else:
        ko(f"empty: rc={rc} stderr={err!r}")


# Inv 8: gate blocks when spec unmodified AND no reason given.
def t_gate_blocks():
    d = os.path.join(TMPROOT, 't_gate_blocks_repo')
    subprocess.run(['git', 'init', d], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.email', 'test@test.com'], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.name', 'Test'], capture_output=True)
    feat = os.path.join(d, 'feat')
    _make_feature_dir(feat, 't_gate_blocks', 'spec-update')
    os.makedirs(os.path.join(feat, 'docs', 'spec'), exist_ok=True)
    with open(os.path.join(feat, 'docs', 'spec', 'spec.md'), 'w') as f:
        f.write('spec content')
    subprocess.run(['git', '-C', d, 'add', '-A'], capture_output=True)
    subprocess.run(['git', '-C', d, 'commit', '-m', 'init'], capture_output=True)
    rc, _, err = _run(
        ['python3', TDD_STEP, 'transition', feat, 'test-red'],
        env={**os.environ, 'RABBIT_ROOT': d},
    )
    with open(os.path.join(feat, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc != 0 and newstate == 'spec-update':
        ok('Inv 8: gate blocks when spec unmodified and no reason')
    else:
        ko(f"gate blocks: rc={rc} state={newstate} stderr={err!r}")


# Inv 8(a): git-diff under docs/spec/ satisfies the gate.
def t_gate_allows_diff():
    d = os.path.join(TMPROOT, 't_gate_allows_repo')
    subprocess.run(['git', 'init', d], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.email', 'test@test.com'], capture_output=True)
    subprocess.run(['git', '-C', d, 'config', 'user.name', 'Test'], capture_output=True)
    feat = os.path.join(d, 'feat')
    _make_feature_dir(feat, 't_gate_allows', 'spec-update')
    os.makedirs(os.path.join(feat, 'docs', 'spec'), exist_ok=True)
    with open(os.path.join(feat, 'docs', 'spec', 'spec.md'), 'w') as f:
        f.write('original spec')
    subprocess.run(['git', '-C', d, 'add', '-A'], capture_output=True)
    subprocess.run(['git', '-C', d, 'commit', '-m', 'init'], capture_output=True)
    with open(os.path.join(feat, 'docs', 'spec', 'spec.md'), 'a') as f:
        f.write('\nupdated spec')
    rc, _, err = _run(
        ['python3', TDD_STEP, 'transition', feat, 'test-red'],
        env={**os.environ, 'RABBIT_ROOT': d},
    )
    with open(os.path.join(feat, 'feature.json')) as f:
        newstate = json.load(f)['tdd_state']
    if rc == 0 and newstate == 'test-red':
        ok('Inv 8: gate allows when spec.md modified in git')
    else:
        ko(f"gate allows: rc={rc} state={newstate} stderr={err!r}")


# Inv 8 cross-check: next from spec-update is test-red (forward target unchanged).
def t_next_is_test_red():
    d = os.path.join(TMPROOT, 't_next_tr')
    _make_feature_dir(d, 't_next_tr', 'spec-update')
    res = subprocess.run(['python3', TDD_STEP, 'next', d], capture_output=True)
    out = res.stdout.decode().strip()
    if res.returncode == 0 and out == 'test-red':
        ok('Inv 8 cross-check: next from spec-update is test-red')
    else:
        ko(f"next: rc={res.returncode} out='{out}'")


print(f"running spec-update gate tests against {TDD_STEP}")
t_reason_allows(); t_reason_persisted()
t_reason_missing_value(); t_reason_empty()
t_gate_blocks(); t_gate_allows_diff()
t_next_is_test_red()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
