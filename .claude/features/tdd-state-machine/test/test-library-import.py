#!/usr/bin/env python3
# test-library-import.py — Inv 13 coverage.
#
# Inv 13: tdd-step.py imports check functions from contract.lib.checks
#         in-process. It MUST NOT fan out via subprocess to
#         .claude/features/contract/scripts/enforcement/check-*.py CLI shims.
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


# Inv 13: source-level references to the library API.
def t_source_imports_library():
    with open(TDD_STEP) as f:
        src = f.read()
    needles = [
        'contract.lib.checks',
        'check_tests_non_interactive',
        'check_numbered_lists',
    ]
    missing = [n for n in needles if n not in src]
    if not missing:
        ok('Inv 13: tdd-step.py source imports contract.lib.checks library API')
    else:
        ko(f"library: missing references in tdd-step.py: {missing}")


# Inv 13: _run_enforcement_checks is defined as a function in tdd-step.py
# and the enforcement check block appears exactly once (no copy-paste duplication).
def t_one_call_site():
    import re
    with open(TDD_STEP) as f:
        content = f.read()
    if not re.search(r'^def _run_enforcement_checks\(', content, re.MULTILINE):
        ko('one-site: _run_enforcement_checks function NOT defined in tdd-step.py')
        return
    count = content.count('checks.check_tests_non_interactive')
    if count == 1:
        ok('Inv 13: enforcement check uses library API at exactly one site')
    else:
        ko(f"one-site: expected 1, found {count}")


# Inv 13: spec-update -> test-red post-write call to _run_spec_update_checks
# appears at exactly one site (de-duplicated across forward and --force branches).
def t_spec_update_one_site():
    with open(TDD_STEP) as f:
        src = f.read()
    n = src.count('_run_spec_update_checks(d, REPO_ROOT)')
    if n == 1:
        ok('Inv 13: _run_spec_update_checks invoked from exactly one site')
    else:
        ko(f"spec-update site: expected 1, found {n}")


# Inv 13: library-based check fires even when NO enforcement CLI dir exists.
# Proof that the library path — not subprocess — is the source of the check.
def t_no_enforcement_dir_needed():
    repo = os.path.join(TMPROOT, 'noenf_repo')
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
    enforcement_dir = os.path.join(repo, '.claude', 'features', 'contract', 'scripts', 'enforcement')
    if os.path.isdir(enforcement_dir):
        ko(f"precondition: enforcement dir unexpectedly present at {enforcement_dir}")
        return
    feat = os.path.join(repo, '.claude', 'features', 'noenf_feat')
    _make_feature_dir(feat, 'noenf_feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and b'R3 check failed' in err:
        ok('Inv 13: library-based check fires without CLI enforcement dir present')
    else:
        ko(f"no-enf: rc={rc} stderr={err!r}")


# Inv 13: source explicitly excludes subprocess to enforcement check-*.py shims.
def t_no_subprocess_to_enforcement():
    with open(TDD_STEP) as f:
        src = f.read()
    # The subprocess module is used legitimately for git diff and rabbit-project.py.
    # We assert no occurrence of an enforcement shim path / name pattern.
    forbidden = ['enforcement/check-', 'scripts/enforcement']
    found = [s for s in forbidden if s in src]
    if not found:
        ok('Inv 13: tdd-step.py source contains no subprocess to enforcement CLI shims')
    else:
        ko(f"no-subproc: forbidden refs in source: {found}")


print(f"running library-import tests against {TDD_STEP}")
t_source_imports_library(); t_one_call_site(); t_spec_update_one_site()
t_no_enforcement_dir_needed(); t_no_subprocess_to_enforcement()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
