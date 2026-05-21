#!/usr/bin/env python3
# test-backlog-4-defensive-branches.py — close test gaps for uncovered
# defensive branches in tdd-step.py.
#
# Owner: rabbit team
# Linked: rabbit/features/tdd-state-machine/backlogs/TDD-STATE-MACHINE-BACKLOG-4
#
# Covers:
#   b1: tdd-step.py read_state -> (None, 2) on malformed feature.json
#   b2: tdd-step.py --spec-no-change-reason without value -> exit 2
#   b3: tdd-step.py --spec-no-change-reason with empty value -> exit 2
#   b4: tdd-step.py _run_enforcement_checks actually invokes the checks
#       (a failing check emits its WARNING via rabbit_print to stderr).
#   b5: tdd-step.py _post_test_green_hooks invokes rabbit-project.py
#       consolidate when project-map.json is present alongside the
#       features directory.
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
    """Run cmd, return (rc, stdout_bytes, stderr_bytes)."""
    res = subprocess.run(cmd, capture_output=True, env=env)
    return res.returncode, res.stdout, res.stderr


# b1: read_state -> exit 2 on malformed feature.json (tdd-step.py:128-130)
def b1():
    d = os.path.join(TMPROOT, 'b1')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        f.write('{ this is not valid json')
    rc, _, err = _run(['python3', TDD_STEP, 'show', d])
    if rc == 2 and b'failed to parse' in err:
        ok('b1: tdd-step.py exits 2 on malformed feature.json')
    else:
        ko(f"b1: rc={rc} stderr={err!r}")


# b2: --spec-no-change-reason without a value -> exit 2
def b2():
    d = os.path.join(TMPROOT, 'b2')
    _make_feature_dir(d, 'b2', 'spec-update')
    rc, _, err = _run(
        ['python3', TDD_STEP, 'transition', d, 'test-red', '--spec-no-change-reason']
    )
    if rc == 2 and b'requires a non-empty reason' in err:
        ok('b2: --spec-no-change-reason missing value -> exit 2')
    else:
        ko(f"b2: rc={rc} stderr={err!r}")


# b3: --spec-no-change-reason with empty string -> exit 2
def b3():
    d = os.path.join(TMPROOT, 'b3')
    _make_feature_dir(d, 'b3', 'spec-update')
    rc, _, err = _run(
        ['python3', TDD_STEP, 'transition', d, 'test-red', '--spec-no-change-reason', '']
    )
    if rc == 2 and b'requires a non-empty reason' in err:
        ok('b3: --spec-no-change-reason empty value -> exit 2')
    else:
        ko(f"b3: rc={rc} stderr={err!r}")


# b4: _run_enforcement_checks calls contract.lib.checks library functions
# (NOT subprocess to CLI scripts) and surfaces a WARNING via rabbit_print on
# stderr when a check's CheckResult.passed is False.
#
# Build a synthetic repo root containing a stub contract/lib/checks.py whose
# library functions return a failing CheckResult; verify the warning lands
# on stderr when a test-green transition fires.
def b4():
    repo = os.path.join(TMPROOT, 'b4_repo')
    contract_scripts = os.path.join(repo, '.claude', 'features', 'contract', 'scripts')
    contract_lib = os.path.join(repo, '.claude', 'features', 'contract', 'lib')
    os.makedirs(contract_scripts, exist_ok=True)
    os.makedirs(contract_lib, exist_ok=True)
    # rabbit_print must be importable from contract/scripts/rabbit_print.py.
    real_rp = os.path.join(FEATURE_DIR, '..', 'contract', 'scripts', 'rabbit_print.py')
    real_rp = os.path.abspath(real_rp)
    if not os.path.isfile(real_rp):
        ko(f"b4: prerequisite rabbit_print.py missing at {real_rp}")
        return
    shutil.copy(real_rp, os.path.join(contract_scripts, 'rabbit_print.py'))
    # Stub contract.lib.checks: every called check returns a failing
    # CheckResult so tdd-step.py emits its warnings via rabbit_print.
    with open(os.path.join(contract_lib, '__init__.py'), 'w') as f:
        f.write('')
    with open(os.path.join(contract_lib, 'checks.py'), 'w') as f:
        f.write(
            'class CheckResult:\n'
            '    def __init__(self, passed, messages=None):\n'
            '        self.passed = passed\n'
            '        self.messages = list(messages) if messages else []\n'
            'def _fail(*a, **k):\n'
            '    return CheckResult(False, ["VIOLATION: stub check failure"])\n'
            'check_tests_non_interactive = _fail\n'
            'check_sentinel = _fail\n'
            'check_naming = _fail\n'
            'check_imports_resolve = _fail\n'
            'check_symlinks_resolve = _fail\n'
            'check_template_producer_consistency = _fail\n'
            'check_numbered_lists = _fail\n'
        )
    # Also need a contract/__init__.py so `contract.lib.checks` imports.
    with open(os.path.join(repo, '.claude', 'features', 'contract', '__init__.py'), 'w') as f:
        f.write('')
    # Feature dir transitioning impl -> test-green.
    feat = os.path.join(repo, '.claude', 'features', 'b4feat')
    _make_feature_dir(feat, 'b4feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, out, err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and b'R3 check failed' in err:
        ok('b4: library-based enforcement check surfaces WARNING on stderr')
    else:
        ko(f"b4: rc={rc} stderr={err!r}")


# b5: _post_test_green_hooks invokes rabbit-project.py consolidate when a
# project-map.json sits beside the features directory.
#
# We stub rabbit-project.py to write a sentinel file, then verify the
# sentinel exists after a test-green transition.
def b5():
    repo = os.path.join(TMPROOT, 'b5_repo')
    project = os.path.join(repo, '.claude', 'b5project')
    features_dir = os.path.join(project, 'features')
    feat = os.path.join(features_dir, 'b5feat')
    _make_feature_dir(feat, 'b5feat', 'impl')
    # project-map.json beside features/
    with open(os.path.join(project, 'project-map.json'), 'w') as f:
        json.dump({"project": "b5project"}, f)
    # Stub rabbit-project.py that writes a sentinel
    onboard_dir = os.path.join(repo, '.claude', 'features', 'rabbit-cage', 'scripts')
    os.makedirs(onboard_dir, exist_ok=True)
    sentinel = os.path.join(TMPROOT, 'b5_sentinel.txt')
    stub = os.path.join(onboard_dir, 'rabbit-project.py')
    with open(stub, 'w') as f:
        f.write(
            '#!/usr/bin/env python3\n'
            'import sys\n'
            f'open({sentinel!r}, "w").write(" ".join(sys.argv[1:]))\n'
            'sys.exit(0)\n'
        )
    os.chmod(stub, 0o755)
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _, _ = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and os.path.isfile(sentinel):
        with open(sentinel) as f:
            args = f.read()
        if 'consolidate' in args and 'b5project' in args:
            ok('b5: project-map.json triggers rabbit-project.py consolidate <project>')
        else:
            ko(f"b5: sentinel args={args!r}")
    else:
        ko(f"b5: rc={rc} sentinel_exists={os.path.isfile(sentinel)}")


print(f"running BACKLOG-4 defensive-branch tests")
b1(); b2(); b3(); b4(); b5()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
