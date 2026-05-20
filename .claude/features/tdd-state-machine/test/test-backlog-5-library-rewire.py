#!/usr/bin/env python3
# test-backlog-5-library-rewire.py — verify Inv 11 + Inv 12 (BACKLOG-5).
#
# Owner: rabbit team
# Linked: rabbit/features/tdd-state-machine/backlogs/TDD-STATE-MACHINE-BACKLOG-5
#
# Inv 11: _run_enforcement_checks uses contract.lib.checks library (not
#         subprocess fan-out to enforcement CLI scripts).
# Inv 12: spec-update -> test-red transition runs check_numbered_lists
#         against the feature's docs/spec/ directory and surfaces a
#         warning on stderr when the check fails; the transition still
#         succeeds (the check is non-blocking).
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


def _build_synthetic_contract(repo, *, check_module_body):
    """Create a synthetic repo with contract.lib.checks stub.

    check_module_body is the Python source for the stub checks module.
    Returns the repo path.
    """
    contract_scripts = os.path.join(repo, '.claude', 'features', 'contract', 'scripts')
    contract_lib = os.path.join(repo, '.claude', 'features', 'contract', 'lib')
    os.makedirs(contract_scripts, exist_ok=True)
    os.makedirs(contract_lib, exist_ok=True)
    real_rp = os.path.abspath(os.path.join(FEATURE_DIR, '..', 'contract', 'scripts', 'rabbit_print.py'))
    shutil.copy(real_rp, os.path.join(contract_scripts, 'rabbit_print.py'))
    with open(os.path.join(repo, '.claude', 'features', 'contract', '__init__.py'), 'w') as f:
        f.write('')
    with open(os.path.join(contract_lib, '__init__.py'), 'w') as f:
        f.write('')
    with open(os.path.join(contract_lib, 'checks.py'), 'w') as f:
        f.write(check_module_body)
    return repo


# r1: _run_enforcement_checks uses contract.lib.checks (no subprocess to CLI
# enforcement scripts). Stub the library to fail and verify warning fires
# even though NO CLI scripts exist under enforcement/.
def r1():
    repo = os.path.join(TMPROOT, 'r1_repo')
    body = (
        'class CheckResult:\n'
        '    def __init__(self, passed, messages=None):\n'
        '        self.passed = passed\n'
        '        self.messages = list(messages) if messages else []\n'
        'def _fail(*a, **k):\n'
        '    return CheckResult(False, ["VIOLATION: stub failure for r1"])\n'
        'check_tests_non_interactive = _fail\n'
        'check_sentinel = _fail\n'
        'check_naming = _fail\n'
        'check_imports_resolve = _fail\n'
        'check_symlinks_resolve = _fail\n'
        'check_template_producer_consistency = _fail\n'
        'check_numbered_lists = _fail\n'
    )
    _build_synthetic_contract(repo, check_module_body=body)
    # Critically: NO enforcement/ directory exists in the synthetic repo.
    # The presence of the warning proves the library path is the source of
    # the check, not subprocess to a CLI script.
    enforcement_dir = os.path.join(repo, '.claude', 'features', 'contract', 'scripts', 'enforcement')
    if os.path.isdir(enforcement_dir):
        ko(f"r1: precondition - enforcement dir unexpectedly present at {enforcement_dir}")
        return
    feat = os.path.join(repo, '.claude', 'features', 'r1feat')
    _make_feature_dir(feat, 'r1feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and b'R3 check failed' in err:
        ok('r1: library-based check fires warning (no CLI enforcement dir present)')
    else:
        ko(f"r1: rc={rc} stderr={err!r}")


# r2: tdd-step.py source imports contract.lib.checks (Inv 11 structural).
def r2():
    with open(TDD_STEP) as f:
        src = f.read()
    needles = [
        'contract.lib.checks',
        'check_tests_non_interactive',
        'check_numbered_lists',
    ]
    missing = [n for n in needles if n not in src]
    if not missing:
        ok('r2: tdd-step.py source imports contract.lib.checks library API')
    else:
        ko(f"r2: missing references in tdd-step.py: {missing}")


# r3: spec-update -> test-red transition runs check_numbered_lists against
# the feature's docs/spec/ directory. Stub the library to fail, supply a
# --spec-no-change-reason (to satisfy the Inv 8 gate), and verify the
# numbered-list warning surfaces on stderr while the transition still
# succeeds.
def r3():
    repo = os.path.join(TMPROOT, 'r3_repo')
    body = (
        'class CheckResult:\n'
        '    def __init__(self, passed, messages=None):\n'
        '        self.passed = passed\n'
        '        self.messages = list(messages) if messages else []\n'
        'def _pass(*a, **k):\n'
        '    return CheckResult(True, ["OK"])\n'
        'def _fail_numbered(*a, **k):\n'
        '    return CheckResult(False, ["spec.md:1: heading-decimal ## 1.1 foo"])\n'
        'check_tests_non_interactive = _pass\n'
        'check_sentinel = _pass\n'
        'check_naming = _pass\n'
        'check_imports_resolve = _pass\n'
        'check_symlinks_resolve = _pass\n'
        'check_template_producer_consistency = _pass\n'
        'check_numbered_lists = _fail_numbered\n'
    )
    _build_synthetic_contract(repo, check_module_body=body)
    feat = os.path.join(repo, '.claude', 'features', 'r3feat')
    _make_feature_dir(feat, 'r3feat', 'spec-update')
    # docs/spec/spec.md needs to exist for the numbered-lists check target.
    spec_dir = os.path.join(feat, 'docs', 'spec')
    os.makedirs(spec_dir, exist_ok=True)
    with open(os.path.join(spec_dir, 'spec.md'), 'w') as f:
        f.write('# title\n## 1.1 sub\n')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(
        ['python3', TDD_STEP, 'transition', feat, 'test-red',
         '--spec-no-change-reason', 'r3 fixture'],
        env=env,
    )
    if rc == 0 and b'numbered-list' in err:
        ok('r3: spec-update -> test-red surfaces check_numbered_lists warning')
    else:
        ko(f"r3: rc={rc} stderr={err!r}")


# r4: when check_numbered_lists passes, no numbered-list warning appears
# (the check is wired but only emits on failure).
def r4():
    repo = os.path.join(TMPROOT, 'r4_repo')
    body = (
        'class CheckResult:\n'
        '    def __init__(self, passed, messages=None):\n'
        '        self.passed = passed\n'
        '        self.messages = list(messages) if messages else []\n'
        'def _pass(*a, **k):\n'
        '    return CheckResult(True, ["OK"])\n'
        'check_tests_non_interactive = _pass\n'
        'check_sentinel = _pass\n'
        'check_naming = _pass\n'
        'check_imports_resolve = _pass\n'
        'check_symlinks_resolve = _pass\n'
        'check_template_producer_consistency = _pass\n'
        'check_numbered_lists = _pass\n'
    )
    _build_synthetic_contract(repo, check_module_body=body)
    feat = os.path.join(repo, '.claude', 'features', 'r4feat')
    _make_feature_dir(feat, 'r4feat', 'spec-update')
    spec_dir = os.path.join(feat, 'docs', 'spec')
    os.makedirs(spec_dir, exist_ok=True)
    with open(os.path.join(spec_dir, 'spec.md'), 'w') as f:
        f.write('# title\n## sub\n')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(
        ['python3', TDD_STEP, 'transition', feat, 'test-red',
         '--spec-no-change-reason', 'r4 fixture'],
        env=env,
    )
    if rc == 0 and b'numbered-list' not in err:
        ok('r4: spec-update -> test-red emits no warning when check passes')
    else:
        ko(f"r4: rc={rc} stderr={err!r}")


print(f"running BACKLOG-5 library-rewire tests")
r1(); r2(); r3(); r4()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
