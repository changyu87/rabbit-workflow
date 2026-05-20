#!/usr/bin/env python3
# test-bug-6-cleanup.py — verify TDD-STATE-MACHINE-BUG-6 fixes.
#
# Owner: rabbit team
# Linked: rabbit/features/tdd-state-machine/bugs/TDD-STATE-MACHINE-BUG-6
#
# BUG-6 covers four cleanup items found after BACKLOG-5:
#
#   r1: check_sentinel must surface a non-empty warning when it fails (Inv 7
#       said "A failed CheckResult emits a warning via rabbit_print on
#       stderr"; the previous code passed warn_msg='' which silently
#       swallowed sentinel failures).
#
#   r2: _load_checks_module must remove the .claude/features/ entry it
#       inserts into sys.path, so embedding callers do not inherit the
#       polluted path. Verified by running tdd-step.py in-process via
#       runpy and asserting sys.path is unchanged after the call.
#
#   r3: the spec-update -> test-red post-write branch must be hoisted into
#       a single block. Verified by counting source-level occurrences of
#       `_run_spec_update_checks(d, REPO_ROOT)` in tdd-step.py — only one
#       call site may exist (previously duplicated across the
#       forward-accepted and --force branches).
#
#   r4: contract.md `reads.files` must declare the whole docs/spec/
#       directory (or include contract.md) since check_numbered_lists
#       walks the directory, not just spec.md.
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')
CONTRACT_MD = os.path.join(FEATURE_DIR, 'docs', 'spec', 'contract.md')
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


# r1: when check_sentinel returns a failed CheckResult, a non-empty warning
# is surfaced on stderr (Inv 7 — no silent swallow). All other checks pass
# so we can pin the warning text to the sentinel call site.
def r1():
    repo = os.path.join(TMPROOT, 'r1_repo')
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
    feat = os.path.join(repo, '.claude', 'features', 'r1feat')
    _make_feature_dir(feat, 'r1feat', 'impl')
    env = {**os.environ, 'RABBIT_ROOT': repo}
    rc, _out, err = _run(['python3', TDD_STEP, 'transition', feat, 'test-green'], env=env)
    if rc == 0 and b'sentinel' in err:
        ok('r1: check_sentinel failure surfaces a warning (no silent swallow)')
    else:
        ko(f"r1: rc={rc} stderr={err!r}")


# r2: in-process call to _load_checks_module must leave sys.path unchanged.
# We import tdd-step as a module via importlib.util, snapshot sys.path,
# invoke _load_checks_module, then assert sys.path is unchanged.
def r2():
    repo = os.path.join(TMPROOT, 'r2_repo')
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
    features_dir = os.path.join(repo, '.claude', 'features')

    # Use a subprocess so we can deterministically capture stdout JSON.
    helper = os.path.join(TMPROOT, 'r2_helper.py')
    with open(helper, 'w') as f:
        f.write(
            'import json, sys, importlib.util, os\n'
            f'spec = importlib.util.spec_from_file_location("tdd_step_under_test", {TDD_STEP!r})\n'
            'mod = importlib.util.module_from_spec(spec)\n'
            'spec.loader.exec_module(mod)\n'
            'before = list(sys.path)\n'
            f'm = mod._load_checks_module({repo!r})\n'
            'after = list(sys.path)\n'
            f'features_dir = {features_dir!r}\n'
            'added = [p for p in after if p not in before]\n'
            'leaked = features_dir in after and features_dir not in before\n'
            'print(json.dumps({"loaded": m is not None, "added": added, "leaked": leaked}))\n'
        )
    rc, out, err = _run(['python3', helper])
    if rc != 0:
        ko(f"r2: helper rc={rc} stderr={err!r}")
        return
    try:
        info = json.loads(out.decode())
    except Exception as e:
        ko(f"r2: bad helper output: {out!r} ({e})")
        return
    if info.get('loaded') and not info.get('leaked') and not info.get('added'):
        ok('r2: _load_checks_module restores sys.path (no features_dir leak)')
    else:
        ko(f"r2: sys.path leaked: {info!r}")


# r3: the spec-update -> test-red post-write call to _run_spec_update_checks
# must appear at exactly one call site in tdd-step.py (de-duplicated across
# the forward and --force branches).
def r3():
    with open(TDD_STEP) as f:
        src = f.read()
    n = src.count('_run_spec_update_checks(d, REPO_ROOT)')
    if n == 1:
        ok('r3: _run_spec_update_checks called from exactly one site in tdd-step.py')
    else:
        ko(f"r3: expected 1 call site for _run_spec_update_checks, found {n}")


# r4: contract.md reads.files must declare the docs/spec/ directory (or
# explicitly include contract.md), since check_numbered_lists walks the
# whole directory.
def r4():
    with open(CONTRACT_MD) as f:
        text = f.read()
    # Parse the JSON block inside the markdown fence.
    start = text.find('```json')
    end = text.find('```', start + len('```json'))
    if start < 0 or end < 0:
        ko('r4: contract.md missing ```json block')
        return
    block = text[start + len('```json'): end].strip()
    try:
        data = json.loads(block)
    except Exception as e:
        ko(f"r4: contract.md JSON parse failure: {e}")
        return
    reads_files = data.get('reads', {}).get('files', [])
    has_dir = any(p.rstrip('/').endswith('docs/spec') for p in reads_files)
    has_contract_md = any(p.endswith('docs/spec/contract.md') for p in reads_files)
    if has_dir or has_contract_md:
        ok('r4: contract.md reads.files declares docs/spec dir or contract.md')
    else:
        ko(f"r4: contract.md reads.files lacks docs/spec dir or contract.md: {reads_files!r}")


print("running BUG-6 cleanup tests")
r1(); r2(); r3(); r4()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
