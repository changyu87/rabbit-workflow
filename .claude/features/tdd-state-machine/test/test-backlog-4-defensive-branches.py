#!/usr/bin/env python3
# test-backlog-4-defensive-branches.py — close test gaps for uncovered
# defensive branches in tdd-step.py, tdd-context.py, tdd-drift-check.py.
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
#   b6: tdd-context.py exits 2 when feature.json is missing.
#   b7: tdd-context.py exits 2 when feature.json is malformed JSON.
#   b8: tdd-drift-check.py exits 2 when test/run.py is missing
#       (state=test-green so the runner is required).
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')
TDD_CTX = os.path.join(FEATURE_DIR, 'scripts', 'tdd-context.py')
TDD_DRIFT = os.path.join(FEATURE_DIR, 'scripts', 'tdd-drift-check.py')
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


# b4: _run_enforcement_checks invokes the actual scripts and surfaces a
# WARNING via rabbit_print on stderr when a check exits non-zero.
#
# Build a synthetic repo root containing a stub enforcement script that
# always exits 1; verify the warning message lands on stderr when a
# test-green transition fires.
def b4():
    repo = os.path.join(TMPROOT, 'b4_repo')
    enforcement_dir = os.path.join(repo, '.claude', 'features', 'contract', 'scripts', 'enforcement')
    os.makedirs(enforcement_dir, exist_ok=True)
    # Stub script that always fails - matches the name tdd-step.py invokes
    # with the warn message "WARNING: R3 check failed for <dir>".
    stub = os.path.join(enforcement_dir, 'check-tests-non-interactive.py')
    with open(stub, 'w') as f:
        f.write('#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n')
    os.chmod(stub, 0o755)
    # rabbit_print must be importable from contract/scripts/rabbit_print.py.
    contract_scripts = os.path.join(repo, '.claude', 'features', 'contract', 'scripts')
    # Symlink the real rabbit_print into the synthetic contract dir so the
    # tdd-step.py import works under RABBIT_ROOT=repo.
    real_rp = os.path.join(FEATURE_DIR, '..', 'contract', 'scripts', 'rabbit_print.py')
    real_rp = os.path.abspath(real_rp)
    if not os.path.isfile(real_rp):
        ko(f"b4: prerequisite rabbit_print.py missing at {real_rp}")
        return
    shutil.copy(real_rp, os.path.join(contract_scripts, 'rabbit_print.py'))
    # Feature dir transitioning impl -> test-green.
    feat = os.path.join(repo, '.claude', 'features', 'b4feat')
    _make_feature_dir(feat, 'b4feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, out, err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and b'R3 check failed' in err:
        ok('b4: failing enforcement check surfaces WARNING on stderr')
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


# b6: tdd-context.py exits 2 when feature.json is missing.
def b6():
    d = os.path.join(TMPROOT, 'b6')
    os.makedirs(d, exist_ok=True)
    rc, _, err = _run(['python3', TDD_CTX, d])
    if rc == 2 and b'no feature.json' in err:
        ok('b6: tdd-context.py exits 2 when feature.json missing')
    else:
        ko(f"b6: rc={rc} stderr={err!r}")


# b7: tdd-context.py exits 2 when feature.json is malformed JSON.
def b7():
    d = os.path.join(TMPROOT, 'b7')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        f.write('{ not json')
    rc, _, err = _run(['python3', TDD_CTX, d])
    if rc == 2 and b'failed to parse' in err:
        ok('b7: tdd-context.py exits 2 on malformed feature.json')
    else:
        ko(f"b7: rc={rc} stderr={err!r}")


# b8: tdd-drift-check.py exits 2 when test/run.py is missing
# (state=test-green requires running the suite; missing runner = invocation error).
def b8():
    d = os.path.join(TMPROOT, 'b8')
    _make_feature_dir(d, 'b8', 'test-green', run_exit=0)
    os.remove(os.path.join(d, 'test', 'run.py'))
    rc, _, err = _run(['python3', TDD_DRIFT, d])
    if rc == 2 and b'missing' in err:
        ok('b8: tdd-drift-check.py exits 2 when test/run.py missing')
    else:
        ko(f"b8: rc={rc} stderr={err!r}")


print(f"running BACKLOG-4 defensive-branch tests")
b1(); b2(); b3(); b4(); b5(); b6(); b7(); b8()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
