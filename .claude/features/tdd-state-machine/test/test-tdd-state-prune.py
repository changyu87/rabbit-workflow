#!/usr/bin/env python3
# test-tdd-state-prune.py — verify review/merged removed from tdd-step.py.
# (Historic tdd-context.py allowed_next_states checks retired in BACKLOG-7
# alongside the script itself.)
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR).decode().strip()
TDD_STEP = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/scripts/tdd-step.py')

PASS = 0
FAIL = 0
TMPDIR_TEST = tempfile.mkdtemp()


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


def make_feature(d, state):
    os.makedirs(d, exist_ok=True)
    data = {
        "name": "test-prune",
        "tdd_state": state,
        "version": "0.1.0",
        "owner": "test",
        "deprecation": {"criterion": "never"},
    }
    with open(os.path.join(d, 'feature.json'), 'w') as f:
        json.dump(data, f)


# 1. review is not a valid state (even with --force)
make_feature(os.path.join(TMPDIR_TEST, 'f1'), 'test-green')
result = subprocess.run(
    ['python3', TDD_STEP, 'transition', os.path.join(TMPDIR_TEST, 'f1'), 'review', '--force'],
    capture_output=True
)
if result.returncode != 0:
    ok("review rejected even with --force")
else:
    fail("review should be invalid state")

# 2. merged is not a valid state (even with --force)
make_feature(os.path.join(TMPDIR_TEST, 'f2'), 'test-green')
result = subprocess.run(
    ['python3', TDD_STEP, 'transition', os.path.join(TMPDIR_TEST, 'f2'), 'merged', '--force'],
    capture_output=True
)
if result.returncode != 0:
    ok("merged rejected even with --force")
else:
    fail("merged should be invalid state")

# 3. next from test-green is deprecated
make_feature(os.path.join(TMPDIR_TEST, 'f3'), 'test-green')
result = subprocess.run(
    ['python3', TDD_STEP, 'next', os.path.join(TMPDIR_TEST, 'f3')],
    capture_output=True, text=True
)
nxt = result.stdout.strip()
if nxt == 'deprecated':
    ok("next from test-green is deprecated")
else:
    fail(f"next from test-green: expected 'deprecated', got '{nxt}'")

# 4. normal forward chain still works: spec -> spec-update
make_feature(os.path.join(TMPDIR_TEST, 'f4'), 'spec')
result = subprocess.run(
    ['python3', TDD_STEP, 'transition', os.path.join(TMPDIR_TEST, 'f4'), 'spec-update'],
    capture_output=True
)
if result.returncode == 0:
    ok("spec -> spec-update still works")
else:
    fail("spec -> spec-update broken")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPDIR_TEST, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
