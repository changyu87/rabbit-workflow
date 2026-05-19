#!/usr/bin/env python3
# test-byte-identical-import.py — Inv 6 regression guard.
#
# For the duration of the import cycle, the three state-machine scripts under
# tdd-state-machine/scripts/ MUST be byte-identical to their counterparts in
# tdd-subagent/scripts/. The follow-up cycle that deletes the tdd-subagent
# originals will replace this with a "present here, absent in tdd-subagent"
# guard.
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

HERE = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/scripts')
ORIG = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/scripts')

SCRIPTS = ['tdd-step.py', 'tdd-context.py', 'tdd-drift-check.py']

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


for name in SCRIPTS:
    here = os.path.join(HERE, name)
    orig = os.path.join(ORIG, name)
    if not os.path.exists(here):
        ko(f"{name}: missing in tdd-state-machine/scripts/")
        continue
    if not os.path.exists(orig):
        ko(f"{name}: missing in tdd-subagent/scripts/")
        continue
    with open(here, 'rb') as f:
        h = f.read()
    with open(orig, 'rb') as f:
        o = f.read()
    if h == o:
        ok(f"{name}: byte-identical to tdd-subagent original")
    else:
        ko(f"{name}: byte mismatch with tdd-subagent original")

# Executable-bit invariant (Inv 3)
for name in SCRIPTS:
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        continue
    mode = os.stat(p).st_mode & 0o777
    if mode & 0o100:
        ok(f"{name}: executable bit set ({oct(mode)})")
    else:
        ko(f"{name}: executable bit not set ({oct(mode)})")

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
