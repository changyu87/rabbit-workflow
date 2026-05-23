#!/usr/bin/env python3
# test-test-green-hooks.py — Inv 10, 11 coverage.
#
# Inv 10: test-green calls six check functions from contract.lib.checks
#         in-process. A non-passed CheckResult emits a non-empty warning
#         via rabbit_print on stderr; the hook never blocks.
# Inv 11: test-green invokes rabbit-project.py consolidate <project> when
#         project-map.json exists in the enclosing project directory; the
#         hook never blocks.
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


# Inv 10: failing checks surface WARNING via rabbit_print on stderr.
def t_enforcement_warning():
    repo = os.path.join(TMPROOT, 'enf_warn')
    body = (
        'class CheckResult:\n'
        '    def __init__(self, passed, messages=None):\n'
        '        self.passed = passed\n'
        '        self.messages = list(messages) if messages else []\n'
        'def _fail(*a, **k):\n'
        '    return CheckResult(False, ["VIOLATION: stub failure"])\n'
        'check_tests_non_interactive = _fail\n'
        'check_sentinel = _fail\n'
        'check_naming = _fail\n'
        'check_imports_resolve = _fail\n'
        'check_symlinks_resolve = _fail\n'
        'check_template_producer_consistency = _fail\n'
        'check_numbered_lists = _fail\n'
    )
    _build_synthetic_contract(repo, check_module_body=body)
    feat = os.path.join(repo, '.claude', 'features', 'enf_warn_feat')
    _make_feature_dir(feat, 'enf_warn_feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and b'R3 check failed' in err:
        ok('Inv 10: library-based enforcement check surfaces WARNING on stderr')
    else:
        ko(f"enf: rc={rc} stderr={err!r}")


# Inv 10: check_sentinel failure surfaces a non-empty warning (no silent swallow).
def t_sentinel_warning():
    repo = os.path.join(TMPROOT, 'sentinel_warn')
    body = (
        'class CheckResult:\n'
        '    def __init__(self, passed, messages=None):\n'
        '        self.passed = passed\n'
        '        self.messages = list(messages) if messages else []\n'
        'def _pass(*a, **k):\n'
        '    return CheckResult(True, ["OK"])\n'
        'def _fail_sentinel(*a, **k):\n'
        '    return CheckResult(False, ["VIOLATION: sentinel stub"])\n'
        'check_tests_non_interactive = _pass\n'
        'check_sentinel = _fail_sentinel\n'
        'check_naming = _pass\n'
        'check_imports_resolve = _pass\n'
        'check_symlinks_resolve = _pass\n'
        'check_template_producer_consistency = _pass\n'
        'check_numbered_lists = _pass\n'
    )
    _build_synthetic_contract(repo, check_module_body=body)
    feat = os.path.join(repo, '.claude', 'features', 'sentinel_feat')
    _make_feature_dir(feat, 'sentinel_feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and b'sentinel' in err:
        ok('Inv 10: check_sentinel failure surfaces warning (no silent swallow)')
    else:
        ko(f"sentinel: rc={rc} stderr={err!r}")


# Inv 10: hook never blocks — transition succeeds even when checks fail.
def t_hook_non_blocking():
    repo = os.path.join(TMPROOT, 'nonblock')
    body = (
        'class CheckResult:\n'
        '    def __init__(self, passed, messages=None):\n'
        '        self.passed = passed\n'
        '        self.messages = list(messages) if messages else []\n'
        'def _fail(*a, **k):\n'
        '    return CheckResult(False, ["VIOLATION"])\n'
        'check_tests_non_interactive = _fail\n'
        'check_sentinel = _fail\n'
        'check_naming = _fail\n'
        'check_imports_resolve = _fail\n'
        'check_symlinks_resolve = _fail\n'
        'check_template_producer_consistency = _fail\n'
        'check_numbered_lists = _fail\n'
    )
    _build_synthetic_contract(repo, check_module_body=body)
    feat = os.path.join(repo, '.claude', 'features', 'nonblock_feat')
    _make_feature_dir(feat, 'nonblock_feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, _err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    with open(os.path.join(feat, 'feature.json')) as f:
        state = json.load(f)['tdd_state']
    if rc == 0 and state == 'test-green':
        ok('Inv 10: hook is non-blocking even when checks fail')
    else:
        ko(f"nonblock: rc={rc} state={state}")


# Inv 11: project-map.json triggers rabbit-project.py consolidate <project>.
def t_project_consolidate():
    repo = os.path.join(TMPROOT, 'consolidate')
    project = os.path.join(repo, '.claude', 'consolidate_project')
    features_dir = os.path.join(project, 'features')
    feat = os.path.join(features_dir, 'consolidate_feat')
    _make_feature_dir(feat, 'consolidate_feat', 'impl')
    with open(os.path.join(project, 'project-map.json'), 'w') as f:
        json.dump({"project": "consolidate_project"}, f)
    onboard_dir = os.path.join(repo, '.claude', 'features', 'rabbit-cage', 'scripts')
    os.makedirs(onboard_dir, exist_ok=True)
    sentinel = os.path.join(TMPROOT, 'consolidate_sentinel.txt')
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
        if 'consolidate' in args and 'consolidate_project' in args:
            ok('Inv 11: project-map.json triggers rabbit-project.py consolidate')
        else:
            ko(f"consolidate: args={args!r}")
    else:
        ko(f"consolidate: rc={rc} sentinel_exists={os.path.isfile(sentinel)}")


# Inv 11: when project-map.json is absent, the hook is silently skipped (never blocks).
def t_no_project_map():
    repo = os.path.join(TMPROOT, 'no_pm')
    feat = os.path.join(repo, '.claude', 'features', 'no_pm_feat')
    _make_feature_dir(feat, 'no_pm_feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _, _ = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    with open(os.path.join(feat, 'feature.json')) as f:
        state = json.load(f)['tdd_state']
    if rc == 0 and state == 'test-green':
        ok('Inv 11: missing project-map.json silently skipped (hook never blocks)')
    else:
        ko(f"no pm: rc={rc} state={state}")


print(f"running test-green hook tests against {TDD_STEP}")
t_enforcement_warning(); t_sentinel_warning(); t_hook_non_blocking()
t_project_consolidate(); t_no_project_map()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
