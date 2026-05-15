#!/usr/bin/env python3
# test-post-transition.py — verify post-transition hooks fire on test-green.
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
    os.makedirs(d, exist_ok=True)
    feature_json = {
        "name": n,
        "version": "0.1.0",
        "owner": "test",
        "tdd_state": s,
    }
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        json.dump(feature_json, f)


# pt1: rebuild-registry.sh hook is NOT present in tdd-step.py (deleted in Task 5).
def pt1():
    with open(TDD_STEP) as f:
        content = f.read()
    if 'rebuild-registry.sh' in content:
        ko('pt1: rebuild-registry.sh reference still present in tdd-step.py')
    else:
        ok('pt1: rebuild-registry.sh hook correctly absent from tdd-step.py')


# pt2: test-green hook NOT called for other transitions (e.g., spec -> spec-update).
def pt2():
    mirror_base = os.path.join(TMPROOT, 'mirror2')
    mirror_tdd_scripts = os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts')
    mirror_contract_scripts = os.path.join(mirror_base, '.claude/features/contract/scripts')
    mirror_features = os.path.join(mirror_base, '.claude/features')
    mirror_feat = os.path.join(mirror_features, 'my-feat')

    os.makedirs(mirror_tdd_scripts, exist_ok=True)
    os.makedirs(mirror_contract_scripts, exist_ok=True)
    os.makedirs(mirror_feat, exist_ok=True)

    shutil.copy(TDD_STEP, os.path.join(mirror_tdd_scripts, 'tdd-step.py'))
    os.chmod(os.path.join(mirror_tdd_scripts, 'tdd-step.py'), 0o755)

    stub = os.path.join(mirror_contract_scripts, 'rebuild-registry.sh')
    with open(stub, 'w') as f:
        f.write('#!/bin/bash\ntouch "$1/../pt2-sentinel"\n')
    os.chmod(stub, 0o755)

    fix(mirror_feat, 'my-feat2', 'spec')

    with open(os.path.join(TMPROOT, 'stdout'), 'w') as out, \
         open(os.path.join(TMPROOT, 'stderr'), 'w') as err:
        result = subprocess.run(
            ['python3', os.path.join(mirror_tdd_scripts, 'tdd-step.py'),
             'transition', mirror_feat, 'spec-update'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': mirror_base}
        )

    expected_sentinel = os.path.join(mirror_base, '.claude', 'pt2-sentinel')
    if result.returncode == 0 and not os.path.exists(expected_sentinel):
        ok('pt2: rebuild-registry.sh NOT called for non-test-green transition')
    else:
        ko(f"pt2: rc={result.returncode} sentinel_exists={'yes' if os.path.exists(expected_sentinel) else 'no'}")


# pt3: --force path to test-green succeeds and does not call rebuild-registry.sh.
def pt3():
    mirror_base = os.path.join(TMPROOT, 'mirror3')
    mirror_tdd_scripts = os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts')
    mirror_contract_scripts = os.path.join(mirror_base, '.claude/features/contract/scripts')
    mirror_features = os.path.join(mirror_base, '.claude/features')
    mirror_feat = os.path.join(mirror_features, 'my-feat')

    os.makedirs(mirror_tdd_scripts, exist_ok=True)
    os.makedirs(mirror_contract_scripts, exist_ok=True)
    os.makedirs(mirror_feat, exist_ok=True)

    shutil.copy(TDD_STEP, os.path.join(mirror_tdd_scripts, 'tdd-step.py'))
    os.chmod(os.path.join(mirror_tdd_scripts, 'tdd-step.py'), 0o755)

    fix(mirror_feat, 'my-feat3', 'spec')

    with open(os.path.join(TMPROOT, 'stdout'), 'w') as out, \
         open(os.path.join(TMPROOT, 'stderr'), 'w') as err:
        result = subprocess.run(
            ['python3', os.path.join(mirror_tdd_scripts, 'tdd-step.py'),
             'transition', mirror_feat, 'test-green', '--force'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': mirror_base}
        )

    unexpected_sentinel = os.path.join(mirror_base, '.claude', 'pt3-sentinel')
    if result.returncode == 0 and not os.path.exists(unexpected_sentinel):
        ok('pt3: --force test-green succeeds; rebuild-registry.sh hook absent (no sentinel)')
    else:
        with open(os.path.join(TMPROOT, 'stderr')) as f:
            err_txt = f.read()
        ko(f"pt3: rc={result.returncode} sentinel_exists={'yes' if os.path.exists(unexpected_sentinel) else 'no'} stderr={err_txt}")


print(f"running post-transition hook tests against {TDD_STEP}")
pt1(); pt2(); pt3()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
