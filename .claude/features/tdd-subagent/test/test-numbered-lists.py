#!/usr/bin/env python3
# test-numbered-lists.py — Inv 12 coverage.
#
# Inv 12: spec-update -> test-red calls contract.lib.checks.check_numbered_lists
#         against <feature-dir>/docs/spec/. A failed CheckResult emits a
#         warning via rabbit_print on stderr but does NOT block.
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
from state_machine_helpers import make_feature_dir as _make_feature_dir  # noqa: E402

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


# Inv 12: failing check_numbered_lists surfaces warning on stderr; transition still succeeds.
def t_warning_fires():
    repo = os.path.join(TMPROOT, 'nl_fail')
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
    feat = os.path.join(repo, '.claude', 'features', 'nl_fail_feat')
    _make_feature_dir(feat, 'nl_fail_feat', 'spec-update')
    spec_dir = os.path.join(feat, 'docs', 'spec')
    os.makedirs(spec_dir, exist_ok=True)
    with open(os.path.join(spec_dir, 'spec.md'), 'w') as f:
        f.write('# title\n## 1.1 sub\n')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(
        ['python3', TDD_STEP, 'transition', feat, 'test-red',
         '--spec-no-change-reason', 'nl-fail fixture'],
        env=env,
    )
    if rc == 0 and b'numbered-list' in err:
        ok('Inv 12: failing check_numbered_lists surfaces warning; transition succeeds')
    else:
        ko(f"nl fail: rc={rc} stderr={err!r}")


# Inv 12: when check_numbered_lists passes, no warning is emitted.
def t_no_warning_on_pass():
    repo = os.path.join(TMPROOT, 'nl_pass')
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
    feat = os.path.join(repo, '.claude', 'features', 'nl_pass_feat')
    _make_feature_dir(feat, 'nl_pass_feat', 'spec-update')
    spec_dir = os.path.join(feat, 'docs', 'spec')
    os.makedirs(spec_dir, exist_ok=True)
    with open(os.path.join(spec_dir, 'spec.md'), 'w') as f:
        f.write('# title\n## sub\n')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(
        ['python3', TDD_STEP, 'transition', feat, 'test-red',
         '--spec-no-change-reason', 'nl-pass fixture'],
        env=env,
    )
    if rc == 0 and b'numbered-list' not in err:
        ok('Inv 12: passing check_numbered_lists emits no warning')
    else:
        ko(f"nl pass: rc={rc} stderr={err!r}")


print(f"running numbered-list check tests against {TDD_STEP}")
t_warning_fires(); t_no_warning_on_pass()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
