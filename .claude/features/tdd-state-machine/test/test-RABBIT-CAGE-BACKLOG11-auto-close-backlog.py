#!/usr/bin/env python3
# test-RABBIT-CAGE-BACKLOG11-auto-close-backlog.py
# Verify that transitioning a feature to test-green auto-closes in-progress backlog items.
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')
BACKLOG_STATUS_SH = os.path.join(FEATURE_DIR, '../rabbit-backlog/scripts/backlog-item-status.py')
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


def setup_mirror(mirror_base, feat_name, feat_state):
    mirror_tdd_scripts = os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts')
    mirror_contract_scripts = os.path.join(mirror_base, '.claude/features/contract/scripts')
    mirror_features = os.path.join(mirror_base, '.claude/features')
    mirror_feat = os.path.join(mirror_features, feat_name)
    mirror_backlog_scripts = os.path.join(mirror_base, '.claude/features/rabbit-backlog/scripts')

    os.makedirs(mirror_tdd_scripts, exist_ok=True)
    os.makedirs(mirror_contract_scripts, exist_ok=True)
    os.makedirs(mirror_feat, exist_ok=True)
    os.makedirs(mirror_backlog_scripts, exist_ok=True)

    # Init git repo so backlog-item-status.py can commit
    subprocess.run(['git', 'init', mirror_base], capture_output=True)
    subprocess.run(['git', '-C', mirror_base, 'config', 'user.email', 'test@test.com'], capture_output=True)
    subprocess.run(['git', '-C', mirror_base, 'config', 'user.name', 'Test'], capture_output=True)
    subprocess.run(['git', '-C', mirror_base, 'commit', '--allow-empty', '-m', 'init'], capture_output=True)

    # Copy tdd-step.py into mirror
    shutil.copy(TDD_STEP, os.path.join(mirror_tdd_scripts, 'tdd-step.py'))
    os.chmod(os.path.join(mirror_tdd_scripts, 'tdd-step.py'), 0o755)

    # Copy backlog-item-status.py into mirror
    shutil.copy(BACKLOG_STATUS_SH, os.path.join(mirror_backlog_scripts, 'backlog-item-status.py'))
    os.chmod(os.path.join(mirror_backlog_scripts, 'backlog-item-status.py'), 0o755)

    # Stub no-op rebuild-registry.sh
    stub = os.path.join(mirror_contract_scripts, 'rebuild-registry.sh')
    with open(stub, 'w') as f:
        f.write('#!/bin/bash\nexit 0\n')
    os.chmod(stub, 0o755)

    # Write feature.json
    feature_json = {
        "name": feat_name,
        "version": "0.1.0",
        "owner": "test",
        "tdd_state": feat_state,
    }
    with open(os.path.join(mirror_feat, 'feature.json'), 'w') as f:
        json.dump(feature_json, f)

    return mirror_feat


def make_backlog_item(mirror_base, feat_name, item_name, status):
    item_dir = os.path.join(mirror_base, f'.claude/backlogs/{feat_name}/{item_name}')
    os.makedirs(item_dir, exist_ok=True)
    item_json = {
        "name": item_name,
        "title": "Test item",
        "status": status,
        "priority": "medium",
        "description": "fixture",
        "owner": "test",
        "filed": "2026-05-11T00:00:00Z",
        "filed_by": "test",
        "closed": None,
        "history": [
            {"ts": "2026-05-11T00:00:00Z", "actor": "test", "action": "opened", "note": "init"}
        ],
    }
    with open(os.path.join(item_dir, 'item.json'), 'w') as f:
        json.dump(item_json, f, indent=2)
    return item_dir


# ab1: in-progress backlog item gets auto-closed on test-green transition.
def ab1():
    mirror_base = os.path.join(TMPROOT, 'ab1')
    feat_dir = setup_mirror(mirror_base, 'my-feat', 'impl')
    item_dir = make_backlog_item(mirror_base, 'my-feat', 'MY-FEAT-BACKLOG-1', 'in-progress')

    with open(os.path.join(TMPROOT, 'ab1.out'), 'w') as out, \
         open(os.path.join(TMPROOT, 'ab1.err'), 'w') as err:
        result = subprocess.run(
            ['python3', os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts/tdd-step.py'),
             'transition', feat_dir, 'test-green'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': mirror_base}
        )

    with open(os.path.join(item_dir, 'item.json')) as f:
        status = json.load(f).get('status', '')

    if result.returncode == 0 and status == 'implemented':
        ok('ab1: in-progress backlog item auto-closed to implemented on test-green')
    else:
        with open(os.path.join(TMPROOT, 'ab1.err')) as f:
            err_txt = f.read()
        ko(f"ab1: rc={result.returncode} item_status={status} stderr={err_txt}")


# ab2: open backlog item is NOT touched (only in-progress items are closed).
def ab2():
    mirror_base = os.path.join(TMPROOT, 'ab2')
    feat_dir = setup_mirror(mirror_base, 'my-feat2', 'impl')
    item_dir = make_backlog_item(mirror_base, 'my-feat2', 'MY-FEAT2-BACKLOG-1', 'open')

    with open(os.path.join(TMPROOT, 'ab2.out'), 'w') as out, \
         open(os.path.join(TMPROOT, 'ab2.err'), 'w') as err:
        result = subprocess.run(
            ['python3', os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts/tdd-step.py'),
             'transition', feat_dir, 'test-green'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': mirror_base}
        )

    with open(os.path.join(item_dir, 'item.json')) as f:
        status = json.load(f).get('status', '')

    if result.returncode == 0 and status == 'open':
        ok('ab2: open backlog item not touched on test-green')
    else:
        with open(os.path.join(TMPROOT, 'ab2.err')) as f:
            err_txt = f.read()
        ko(f"ab2: rc={result.returncode} item_status={status} stderr={err_txt}")


# ab3: no backlog dir — transition still succeeds (best-effort).
def ab3():
    mirror_base = os.path.join(TMPROOT, 'ab3')
    feat_dir = setup_mirror(mirror_base, 'my-feat3', 'impl')
    # No backlog dir created

    with open(os.path.join(TMPROOT, 'ab3.out'), 'w') as out, \
         open(os.path.join(TMPROOT, 'ab3.err'), 'w') as err:
        result = subprocess.run(
            ['python3', os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts/tdd-step.py'),
             'transition', feat_dir, 'test-green'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': mirror_base}
        )

    if result.returncode == 0:
        ok('ab3: test-green transition succeeds when no backlog dir exists')
    else:
        with open(os.path.join(TMPROOT, 'ab3.err')) as f:
            err_txt = f.read()
        ko(f"ab3: rc={result.returncode} stderr={err_txt}")


# ab4: multiple in-progress items — all get auto-closed.
def ab4():
    mirror_base = os.path.join(TMPROOT, 'ab4')
    feat_dir = setup_mirror(mirror_base, 'my-feat4', 'impl')
    item1 = make_backlog_item(mirror_base, 'my-feat4', 'MY-FEAT4-BACKLOG-1', 'in-progress')
    item2 = make_backlog_item(mirror_base, 'my-feat4', 'MY-FEAT4-BACKLOG-2', 'in-progress')

    with open(os.path.join(TMPROOT, 'ab4.out'), 'w') as out, \
         open(os.path.join(TMPROOT, 'ab4.err'), 'w') as err:
        result = subprocess.run(
            ['python3', os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts/tdd-step.py'),
             'transition', feat_dir, 'test-green'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': mirror_base}
        )

    with open(os.path.join(item1, 'item.json')) as f:
        s1 = json.load(f).get('status', '')
    with open(os.path.join(item2, 'item.json')) as f:
        s2 = json.load(f).get('status', '')

    if result.returncode == 0 and s1 == 'implemented' and s2 == 'implemented':
        ok('ab4: multiple in-progress items all auto-closed on test-green')
    else:
        with open(os.path.join(TMPROOT, 'ab4.err')) as f:
            err_txt = f.read()
        ko(f"ab4: rc={result.returncode} s1={s1} s2={s2} stderr={err_txt}")


# ab5: --force path also auto-closes in-progress backlog items.
def ab5():
    mirror_base = os.path.join(TMPROOT, 'ab5')
    feat_dir = setup_mirror(mirror_base, 'my-feat5', 'spec')
    item_dir = make_backlog_item(mirror_base, 'my-feat5', 'MY-FEAT5-BACKLOG-1', 'in-progress')

    with open(os.path.join(TMPROOT, 'ab5.out'), 'w') as out, \
         open(os.path.join(TMPROOT, 'ab5.err'), 'w') as err:
        result = subprocess.run(
            ['python3', os.path.join(mirror_base, '.claude/features/tdd-state-machine/scripts/tdd-step.py'),
             'transition', feat_dir, 'test-green', '--force'],
            stdout=out, stderr=err,
            env={**os.environ, 'RABBIT_ROOT': mirror_base}
        )

    with open(os.path.join(item_dir, 'item.json')) as f:
        status = json.load(f).get('status', '')

    if result.returncode == 0 and status == 'implemented':
        ok('ab5: in-progress backlog item auto-closed on --force test-green')
    else:
        with open(os.path.join(TMPROOT, 'ab5.err')) as f:
            err_txt = f.read()
        ko(f"ab5: rc={result.returncode} item_status={status} stderr={err_txt}")


print(f"running auto-close backlog tests against {TDD_STEP}")
ab1(); ab2(); ab3(); ab4(); ab5()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
