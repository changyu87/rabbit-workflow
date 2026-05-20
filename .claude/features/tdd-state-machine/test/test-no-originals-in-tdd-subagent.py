#!/usr/bin/env python3
# test-no-originals-in-tdd-subagent.py — Inv 6 (post-import-cycle) guard.
#
# After the import + slim cycles, tdd-state-machine OWNS tdd-step.py,
# tdd-context.py, tdd-drift-check.py. The three scripts MUST:
#   - exist in .claude/features/tdd-state-machine/scripts/
#   - NOT exist in .claude/features/tdd-subagent/scripts/
# Also retains the executable-bit check (Inv 3 — executable bit set;
# any user-executable mode is acceptable).
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

HERE = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/scripts')
SUBAGENT = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/scripts')

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
    subagent = os.path.join(SUBAGENT, name)
    if os.path.exists(here):
        ok(f"{name}: present in tdd-state-machine/scripts/")
    else:
        ko(f"{name}: missing in tdd-state-machine/scripts/")
    if os.path.exists(subagent):
        ko(f"{name}: must NOT be present in tdd-subagent/scripts/ (originals deleted)")
    else:
        ok(f"{name}: absent from tdd-subagent/scripts/ as required")

# Executable-bit invariant (Inv 3 — relaxed: executable bit set, any user-exec mode ok).
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
