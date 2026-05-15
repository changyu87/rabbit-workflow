#!/usr/bin/env python3
# Tests for dispatch-tdd-subagent.py --linked-item / --item-type parameters.
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
SCRIPTS_DIR = os.path.join(FEATURE_DIR, 'scripts')
DISPATCH_SH = os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py')
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
    with open(os.path.join(root, '.claude/features/tdd-subagent/docs/spec/contract.md'), 'w') as f:
        f.write('# Contract\nMinimal contract content.')


# t1: --linked-item --item-type bug is accepted (replaces old --bug)
def t1():
    root = os.path.join(TMPROOT, 't1_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/some/bug/dir', '--item-type', 'bug'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if result.returncode == 0 and result.stdout.strip():
        ok('t1: --linked-item --item-type bug accepted, exits 0 with non-empty stdout')
    else:
        ko(f"t1: rc={result.returncode}; expected 0. stderr/stdout: {result.stdout}{result.stderr}")


# t2: --linked-item --item-type backlog is accepted (replaces old --backlog)
def t2():
    root = os.path.join(TMPROOT, 't2_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/some/backlog/item', '--item-type', 'backlog'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if result.returncode == 0 and result.stdout.strip():
        ok('t2: --linked-item --item-type backlog accepted, exits 0 with non-empty stdout')
    else:
        ko(f"t2: rc={result.returncode}; expected 0. stderr/stdout: {result.stdout}{result.stderr}")


# t3: when --linked-item bug is given, emitted prompt contains tdd-report-<feature>.json
def t3():
    root = os.path.join(TMPROOT, 't3_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/bugs/my-bug', '--item-type', 'bug'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if 'tdd-report-tdd-subagent.json' in result.stdout:
        ok("t3: prompt contains 'tdd-report-tdd-subagent.json'")
    else:
        ko("t3: 'tdd-report-tdd-subagent.json' not found in prompt")


# t4: when --linked-item bug is given, emitted prompt contains the bug dir path
def t4():
    root = os.path.join(TMPROOT, 't4_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/bugs/my-bug', '--item-type', 'bug'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if '/bugs/my-bug' in result.stdout:
        ok('t4: prompt contains the linked-item dir path')
    else:
        ko("t4: linked-item dir path '/bugs/my-bug' not found in prompt")


# t5: when --linked-item bug is given, emitted prompt contains spec_compliance
def t5():
    root = os.path.join(TMPROOT, 't5_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/bugs/my-bug', '--item-type', 'bug'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if 'spec_compliance' in result.stdout:
        ok("t5: prompt contains 'spec_compliance' field")
    else:
        ko("t5: 'spec_compliance' not found in prompt")


# t6: when --linked-item backlog is given, emitted prompt contains tdd-report-<feature>.json
def t6():
    root = os.path.join(TMPROOT, 't6_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/backlogs/my-item', '--item-type', 'backlog'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if 'tdd-report-tdd-subagent.json' in result.stdout:
        ok("t6: prompt contains 'tdd-report-tdd-subagent.json'")
    else:
        ko("t6: 'tdd-report-tdd-subagent.json' not found in prompt")


# t7: when --linked-item backlog is given, emitted prompt contains the item dir path
def t7():
    root = os.path.join(TMPROOT, 't7_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/backlogs/my-item', '--item-type', 'backlog'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if '/backlogs/my-item' in result.stdout:
        ok('t7: prompt contains the linked-item dir path')
    else:
        ko("t7: backlog item dir path '/backlogs/my-item' not found in prompt")


# t8: when --linked-item backlog is given, emitted prompt contains spec_compliance field
def t8():
    root = os.path.join(TMPROOT, 't8_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/backlogs/my-item', '--item-type', 'backlog'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if 'spec_compliance' in result.stdout:
        ok("t8: prompt contains 'spec_compliance' field")
    else:
        ko("t8: 'spec_compliance' not found in prompt")


# t9: when neither --linked-item nor --item-type is given, prompt is still valid
def t9():
    root = os.path.join(TMPROOT, 't9_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if result.returncode == 0 and result.stdout.strip():
        ok('t9: baseline (no --linked-item) still exits 0')
    else:
        ko(f"t9: baseline broke: rc={result.returncode}")


# t10: emitted prompt contains HANDOFF section
def t10():
    root = os.path.join(TMPROOT, 't10_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', DISPATCH_SH, '--scope', 'tdd-subagent', '--spec', spec,
         '--linked-item', '/bugs/my-bug', '--item-type', 'bug'],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if 'HANDOFF' in result.stdout.upper():
        ok('t10: prompt contains HANDOFF section')
    else:
        ko("t10: 'HANDOFF' not found in prompt")


print("running dispatch-tdd-bug-backlog-params tests")
print(f"  DISPATCH_SH={DISPATCH_SH}")
print()
t1(); t2(); t3(); t4(); t5(); t6(); t7(); t8(); t9(); t10()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
