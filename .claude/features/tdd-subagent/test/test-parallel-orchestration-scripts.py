#!/usr/bin/env python3
# Tests for dispatch-tdd-subagent.py.
# resolve-feature-scope.sh was deleted in Task 5 (replaced by rabbit-feature-scope feature).
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
SCRIPTS_DIR = os.path.join(FEATURE_DIR, 'scripts')
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

    feature_json = {
        "name": "tdd-subagent",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "fixture feature",
    }
    with open(os.path.join(root, '.claude/features/tdd-subagent/feature.json'), 'w') as f:
        json.dump(feature_json, f)

    shutil.copy(FIND_FEATURE_PY, os.path.join(root, '.claude/features/contract/scripts/find-feature.py'))
    os.chmod(os.path.join(root, '.claude/features/contract/scripts/find-feature.py'), 0o755)

    with open(os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md'), 'w') as f:
        f.write('# Spec\nMinimal spec content.')
    with open(os.path.join(root, '.claude/features/tdd-subagent/docs/spec/contract.md'), 'w') as f:
        f.write('# Contract\nMinimal contract content.')


# t1: resolve-feature-scope.sh does NOT exist (deleted in Task 5)
def t1():
    if not os.path.exists(os.path.join(SCRIPTS_DIR, 'resolve-feature-scope.sh')):
        ok('t1: resolve-feature-scope.sh correctly absent (deleted in Task 5)')
    else:
        ko('t1: resolve-feature-scope.sh still exists but should have been deleted')


# t4: dispatch-tdd-subagent.py exists and is executable
def t4():
    dispatch = os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py')
    if os.path.isfile(dispatch) and os.access(dispatch, os.X_OK):
        ok('t4: dispatch-tdd-subagent.py exists and is executable')
    else:
        ko(f"t4: dispatch-tdd-subagent.py not found or not executable at {dispatch}")


# t5: dispatch-tdd-subagent.py exits 0 and emits non-empty stdout
def t5():
    root = os.path.join(TMPROOT, 't5_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py'),
         '--scope', 'tdd-subagent', '--spec', spec],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if result.returncode == 0 and result.stdout.strip():
        ok('t5: dispatch-tdd-subagent.py exits 0 with non-empty stdout')
    else:
        ko(f"t5: rc={result.returncode} stdout_empty={'yes' if not result.stdout.strip() else 'no'}")


# t6: dispatch-tdd-subagent.py stdout contains "SCOPE"
def t6():
    root = os.path.join(TMPROOT, 't6_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py'),
         '--scope', 'tdd-subagent', '--spec', spec],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if 'SCOPE' in result.stdout:
        ok("t6: dispatch-tdd-subagent.py output contains 'SCOPE'")
    else:
        ko("t6: 'SCOPE' not found in output")


# t7: dispatch-tdd-subagent.py stdout contains "SPEC-READ" (9-step step name)
def t7():
    root = os.path.join(TMPROOT, 't7_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py'),
         '--scope', 'tdd-subagent', '--spec', spec],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if 'SPEC-READ' in result.stdout:
        ok("t7: dispatch-tdd-subagent.py output contains 'SPEC-READ'")
    else:
        ko("t7: 'SPEC-READ' not found in output")


# t8: dispatch-tdd-subagent.py stdout contains ".rabbit-scope-active-"
def t8():
    root = os.path.join(TMPROOT, 't8_root')
    make_rabbit_root(root)
    spec = os.path.join(root, '.claude/features/tdd-subagent/docs/spec/spec.md')
    result = subprocess.run(
        ['python3', os.path.join(SCRIPTS_DIR, 'dispatch-tdd-subagent.py'),
         '--scope', 'tdd-subagent', '--spec', spec],
        capture_output=True, text=True,
        env={**os.environ, 'RABBIT_ROOT': root}
    )
    if '.rabbit-scope-active-' in result.stdout:
        ok("t8: dispatch-tdd-subagent.py output contains '.rabbit-scope-active-'")
    else:
        ko("t8: '.rabbit-scope-active-' not found in output")


print("running parallel-orchestration-scripts tests")
print(f"  SCRIPTS_DIR={SCRIPTS_DIR}")
print()
t1(); t4(); t5(); t6(); t7(); t8()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
