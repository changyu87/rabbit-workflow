#!/usr/bin/env python3
# test-python-only-tech-stack.py
# Asserts: Python is the sole scripting tech stack.
# - tdd-drift-check.py invokes test/run.py (not run.sh) via python3 (not bash)
# - Test fixtures use run.py, not run.sh
# - spec.md declares Python-only stack and has no .sh script paths in Surface/Invariants
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR).decode().strip()

DRIFT_CHECK = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/scripts/tdd-drift-check.py')
SPEC_MD = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/docs/spec/spec.md')
TEST_DRIFT = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/test/test-drift-check.py')
TEST_TDD_STEP = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/test/test-tdd-step.py')
TEST_CONTEXT = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/test/test-context.py')

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


with open(DRIFT_CHECK) as f:
    drift_content = f.read()

with open(SPEC_MD) as f:
    spec_content = f.read()

with open(TEST_DRIFT) as f:
    test_drift_content = f.read()

with open(TEST_TDD_STEP) as f:
    test_step_content = f.read()

with open(TEST_CONTEXT) as f:
    test_ctx_content = f.read()

# t1: tdd-drift-check.py looks for run.py, not run.sh
if 'run.py' in drift_content and 'run.sh' not in drift_content:
    ok('t1: tdd-drift-check.py uses run.py (not run.sh)')
else:
    fail('t1: tdd-drift-check.py still references run.sh or missing run.py')

# t2: tdd-drift-check.py invokes via python3, not bash
if re.search(r'python3', drift_content) and not re.search(r'"bash"', drift_content):
    ok('t2: tdd-drift-check.py invokes via python3 (not bash)')
else:
    fail('t2: tdd-drift-check.py still uses bash invocation')

# t3: spec.md has a Python-only tech stack declaration
if 'Python 3' in spec_content and 'Bash is not used' in spec_content:
    ok('t3: spec.md declares Python-only tech stack')
else:
    fail('t3: spec.md missing Python-only tech stack declaration')

# t4: spec.md Surface section does not reference .sh scripts
surface_match = re.search(r'## Surface(.*?)## Invariants', spec_content, re.DOTALL)
if surface_match:
    surface_text = surface_match.group(1)
    if '.sh' not in surface_text:
        ok('t4: spec.md Surface section has no .sh references')
    else:
        fail('t4: spec.md Surface section still contains .sh reference(s)')
else:
    fail('t4: could not locate Surface section in spec.md')

# t5: test-drift-check.py fixtures use run.py (not run.sh)
if 'run.py' in test_drift_content and 'run.sh' not in test_drift_content:
    ok('t5: test-drift-check.py fixtures use run.py (not run.sh)')
else:
    fail('t5: test-drift-check.py fixtures still reference run.sh or missing run.py')

# t6: test-tdd-step.py fixtures use run.py (not run.sh)
if 'run.py' in test_step_content and 'run.sh' not in test_step_content:
    ok('t6: test-tdd-step.py fixtures use run.py (not run.sh)')
else:
    fail('t6: test-tdd-step.py fixtures still reference run.sh or missing run.py')

# t7: test-context.py fixtures use run.py (not run.sh)
if 'run.py' in test_ctx_content and 'run.sh' not in test_ctx_content:
    ok('t7: test-context.py fixtures use run.py (not run.sh)')
else:
    fail('t7: test-context.py fixtures still reference run.sh or missing run.py')

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
