#!/usr/bin/env python3
# test-script-presence.py — Inv 36, 37 coverage.
#
# Inv 36: scripts/tdd-step.py lives at
#         .claude/features/tdd-subagent/scripts/tdd-step.py.
#         (The second clause of Inv 36 — `.claude/features/tdd-state-machine/`
#         MUST NOT exist — is enforced by a follow-up cleanup touch that
#         removes the absorbed feature directory. That cross-feature deletion
#         is intentionally out of scope for the tdd-subagent dispatch.)
# Inv 37: tdd-step.py has the user-executable bit set (any mode satisfying
#         mode & 0o100).
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

HERE = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/scripts')

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


# Inv 36: presence under tdd-subagent/scripts/.
for name in OWNED_SCRIPTS:
    here = os.path.join(HERE, name)
    if os.path.exists(here):
        ok(f"Inv 36: {name} present in tdd-subagent/scripts/")
    else:
        ko(f"Inv 36: {name} missing in tdd-subagent/scripts/")

# Inv 37: executable bit set.
for name in OWNED_SCRIPTS:
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        continue
    mode = os.stat(p).st_mode & 0o777
    if mode & 0o100:
        ok(f"Inv 37: {name} executable bit set ({oct(mode)})")
    else:
        ko(f"Inv 37: {name} executable bit not set ({oct(mode)})")

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
