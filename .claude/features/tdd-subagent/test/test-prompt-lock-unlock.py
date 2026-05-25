#!/usr/bin/env python3
"""Inv 12 — LOCK uses only touch (no trap); UNLOCK does explicit rm
after chore commit, before HANDOFF."""
import re

from _helpers import run_dispatch, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


res = run_dispatch()
if res.returncode != 0:
    print(f"FATAL: dispatch failed rc={res.returncode}: {res.stderr}")
    raise SystemExit(1)
prompt = res.stdout

# Inv 12: LOCK section uses 'touch' but not 'trap'.
lock_match = re.search(r"STEP 1 — LOCK\n═+\n(.*?)\n═+\nSTEP 2", prompt, re.DOTALL)
if not lock_match:
    ko("inv12: STEP 1 LOCK section not isolated")
else:
    lock_body = lock_match.group(1)
    if "touch " in lock_body and ".rabbit-scope-active-tdd-subagent" in lock_body:
        ok("inv12: LOCK uses touch <repo_root>/.rabbit-scope-active-<feature>")
    else:
        ko("inv12: LOCK missing touch invocation")
    # Inv 12: no actual `trap '<handler>' EXIT` invocation. The LOCK
    # section legitimately discusses traps in prose ("Do NOT register a
    # `trap ...`"), so this checks for the executable trap syntax only.
    if not re.search(r"^\s*trap '", lock_body, re.MULTILINE) and not re.search(
        r"^\s*trap \"", lock_body, re.MULTILINE
    ):
        ok("inv12: LOCK contains no executable `trap '...'` invocation")
    else:
        ko("inv12: LOCK contains an executable `trap '...'` invocation")

# Inv 12: UNLOCK section does explicit rm of the per-feature marker.
unlock_match = re.search(r"STEP 7 — UNLOCK\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
if not unlock_match:
    ko("inv12: STEP 7 UNLOCK section not isolated")
else:
    unlock_body = unlock_match.group(1)
    if re.search(r"rm -f \S+\.rabbit-scope-active-tdd-subagent", unlock_body):
        ok("inv12: UNLOCK has explicit `rm -f <root>/.rabbit-scope-active-<feature>`")
    else:
        ko("inv12: UNLOCK missing explicit rm of scope marker")
    if 'chore(tdd-subagent): advance tdd_state to test-green' in unlock_body:
        ok("inv12: UNLOCK chore commit precedes rm (within UNLOCK section)")
    else:
        ko("inv12: UNLOCK missing chore commit before rm")

report(passed, failed)
