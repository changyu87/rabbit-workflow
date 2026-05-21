#!/usr/bin/env python3
# Tests for dispatch-tdd-subagent.py --linked-items multi-item resolution (BUG-2).
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
SCRIPTS_DIR = os.path.join(FEATURE_DIR, 'scripts')
DISPATCH = os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py')
TMPROOT = tempfile.mkdtemp()

FIND_FEATURE_PY = os.path.join(
    os.path.abspath(os.path.join(SCRIPT_DIR, '../..')),
    'contract', 'scripts', 'find-feature.py'
)

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


def make_rabbit_root(root):
    os.makedirs(os.path.join(root, '.claude/features/tdd-subagent/docs/spec'), exist_ok=True)
    os.makedirs(os.path.join(root, '.claude/features/contract/scripts'), exist_ok=True)

    shutil.copy(FIND_FEATURE_PY, os.path.join(root, '.claude/features/contract/scripts/find-feature.py'))
    os.chmod(os.path.join(root, '.claude/features/contract/scripts/find-feature.py'), 0o755)

    feature_json = {
        "name": "tdd-subagent",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "fixture feature",
    }
    with open(os.path.join(root, '.claude/features/tdd-subagent/feature.json'), 'w') as f:
        json.dump(feature_json, f)

    with open(os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md'), 'w') as f:
        f.write('# Spec\nMinimal spec content.')


def run_dispatch(root, extra_args):
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    return subprocess.run(
        ['python3', DISPATCH, '--scope', 'tdd-subagent', '--spec', spec] + extra_args,
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )


# t1: valid single secondary alongside primary --linked-item
def t1():
    root = os.path.join(TMPROOT, 't1_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-item', '/bugs/primary-bug', '--item-type', 'bug',
        '--linked-items', 'rabbit-cage:bug:RABBIT-CAGE-BUG-9',
    ])
    if r.returncode != 0:
        ko(f"t1: rc={r.returncode}, stderr={r.stderr}")
        return
    p = r.stdout
    # Must mention primary close call (item-status.py with primary path OR id reference)
    # And must mention secondary close call referencing the triple components
    has_primary = '/bugs/primary-bug' in p
    has_secondary_feature = 'rabbit-cage' in p
    has_secondary_id = 'RABBIT-CAGE-BUG-9' in p
    has_item_status = 'item-status.py' in p
    if has_primary and has_secondary_feature and has_secondary_id and has_item_status:
        ok("t1: prompt contains primary + secondary close call references")
    else:
        ko(f"t1: missing one of: primary={has_primary} sec_feat={has_secondary_feature} sec_id={has_secondary_id} item_status={has_item_status}")


# t2: valid multiple secondaries
def t2():
    root = os.path.join(TMPROOT, 't2_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-item', '/bugs/primary-bug', '--item-type', 'bug',
        '--linked-items', 'rabbit-cage:bug:RABBIT-CAGE-BUG-9,rabbit-file:backlog:RF-BL-3',
    ])
    if r.returncode != 0:
        ko(f"t2: rc={r.returncode}, stderr={r.stderr}")
        return
    p = r.stdout
    checks = [
        ('rabbit-cage', 'rabbit-cage' in p),
        ('RABBIT-CAGE-BUG-9', 'RABBIT-CAGE-BUG-9' in p),
        ('rabbit-file', 'rabbit-file' in p),
        ('RF-BL-3', 'RF-BL-3' in p),
    ]
    if all(v for _, v in checks):
        ok("t2: prompt references all secondary items")
    else:
        missing = [name for name, v in checks if not v]
        ko(f"t2: missing references: {missing}")


# t3: malformed — missing colon
def t3():
    root = os.path.join(TMPROOT, 't3_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-items', 'rabbit-cage:bug',
    ])
    if r.returncode == 0:
        ko("t3: malformed triple should exit non-zero")
        return
    if r.stdout.strip():
        ko(f"t3: prompt should NOT be emitted on stdout when malformed; got stdout len={len(r.stdout)}")
        return
    if 'rabbit-cage:bug' in r.stderr:
        ok("t3: malformed triple rejected; stderr names offending entry")
    else:
        ko(f"t3: stderr should name offending entry. stderr={r.stderr}")


# t4: malformed — invalid type
def t4():
    root = os.path.join(TMPROOT, 't4_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-items', 'rabbit-cage:invalid:RABBIT-CAGE-BUG-1',
    ])
    if r.returncode == 0:
        ko("t4: invalid type should exit non-zero")
        return
    if r.stdout.strip():
        ko("t4: prompt should NOT be emitted when type invalid")
        return
    if 'invalid' in r.stderr or 'bug' in r.stderr or 'backlog' in r.stderr:
        ok("t4: invalid-type rejected with informative stderr")
    else:
        ko(f"t4: stderr should mention type validity. stderr={r.stderr}")


# t5: malformed — empty feature field
def t5():
    root = os.path.join(TMPROOT, 't5_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-items', ':bug:RABBIT-CAGE-BUG-1',
    ])
    if r.returncode == 0:
        ko("t5: empty feature field should exit non-zero")
        return
    if r.stdout.strip():
        ko("t5: prompt should NOT be emitted when empty field present")
        return
    ok("t5: empty-field triple rejected")


# t6: primary --linked-item alone produces single close path
def t6():
    root = os.path.join(TMPROOT, 't6_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-item', '/bugs/only-primary', '--item-type', 'bug',
    ])
    if r.returncode != 0:
        ko(f"t6: rc={r.returncode}")
        return
    p = r.stdout
    if '/bugs/only-primary' in p:
        ok("t6: primary --linked-item alone is referenced in prompt")
    else:
        ko("t6: primary item path missing from prompt")


# t7: no linked items at all — no close calls
def t7():
    root = os.path.join(TMPROOT, 't7_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [])
    if r.returncode != 0:
        ko(f"t7: rc={r.returncode}")
        return
    p = r.stdout
    # When no items, item-status.py close calls should not be templated in
    if 'item-status.py' not in p and 'bug-status.py' not in p:
        ok("t7: no close calls in prompt when no linked items provided")
    else:
        ko("t7: close-call references should not appear when no items provided")


# t8: HANDOFF block lists all closed items (primary + secondaries) in closed_items field
def t8():
    root = os.path.join(TMPROOT, 't8_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-item', '/bugs/primary-bug', '--item-type', 'bug',
        '--linked-items', 'rabbit-cage:bug:RABBIT-CAGE-BUG-9,rabbit-file:backlog:RF-BL-3',
    ])
    if r.returncode != 0:
        ko(f"t8: rc={r.returncode}, stderr={r.stderr}")
        return
    p = r.stdout
    # Find HANDOFF section
    idx = p.find('HANDOFF')
    if idx < 0:
        ko("t8: HANDOFF section missing")
        return
    handoff = p[idx:]
    has_closed_items = 'closed_items' in handoff
    has_secondary_in_handoff = 'RABBIT-CAGE-BUG-9' in handoff and 'RF-BL-3' in handoff
    if has_closed_items and has_secondary_in_handoff:
        ok("t8: HANDOFF lists closed_items with all secondaries")
    else:
        ko(f"t8: HANDOFF closed_items missing or incomplete; closed_items={has_closed_items} sec_in_handoff={has_secondary_in_handoff}")


# t9: --linked-items only (no primary --linked-item) is acceptable
def t9():
    root = os.path.join(TMPROOT, 't9_root')
    make_rabbit_root(root)
    r = run_dispatch(root, [
        '--linked-items', 'rabbit-cage:bug:RABBIT-CAGE-BUG-9',
    ])
    if r.returncode != 0:
        ko(f"t9: rc={r.returncode}, stderr={r.stderr}")
        return
    p = r.stdout
    if 'RABBIT-CAGE-BUG-9' in p and 'item-status.py' in p:
        ok("t9: --linked-items works standalone without primary")
    else:
        ko("t9: standalone --linked-items did not emit close call")


print("running dispatch-tdd --linked-items tests")
print(f"  DISPATCH={DISPATCH}")
print()
t1(); t2(); t3(); t4(); t5(); t6(); t7(); t8(); t9()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
