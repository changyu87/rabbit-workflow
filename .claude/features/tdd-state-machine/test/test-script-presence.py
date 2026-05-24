#!/usr/bin/env python3
# test-script-presence.py — Inv 6, 7 coverage.
#
# Inv 6: tdd-state-machine OWNS exactly one script: tdd-step.py.
#        Present in .claude/features/tdd-state-machine/scripts/.
#        Absent from .claude/features/tdd-subagent/scripts/.
# Inv 7: tdd-step.py has the user-executable bit set (any mode satisfying
#        mode & 0o100).
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

HERE = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/scripts')
SUBAGENT = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/scripts')

OWNED_SCRIPTS = ['tdd-step.py']

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


# Inv 6: presence here, absence in tdd-subagent.
for name in OWNED_SCRIPTS:
    here = os.path.join(HERE, name)
    subagent = os.path.join(SUBAGENT, name)
    if os.path.exists(here):
        ok(f"Inv 6: {name} present in tdd-state-machine/scripts/")
    else:
        ko(f"Inv 6: {name} missing in tdd-state-machine/scripts/")
    if os.path.exists(subagent):
        ko(f"Inv 6: {name} must NOT be present in tdd-subagent/scripts/")
    else:
        ok(f"Inv 6: {name} absent from tdd-subagent/scripts/ as required")

# Inv 7: executable bit set.
for name in OWNED_SCRIPTS:
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        continue
    mode = os.stat(p).st_mode & 0o777
    if mode & 0o100:
        ok(f"Inv 7: {name} executable bit set ({oct(mode)})")
    else:
        ko(f"Inv 7: {name} executable bit not set ({oct(mode)})")

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
