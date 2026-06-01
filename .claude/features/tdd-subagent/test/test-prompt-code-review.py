#!/usr/bin/env python3
"""Inv 17 — CODE-REVIEW invokes Skill("superpowers:requesting-code-review")
exactly (case-sensitive)."""
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

cr_match = re.search(r"STEP 6 — CODE-REVIEW\n═+\n(.*?)\n═+\nSTEP 7", prompt, re.DOTALL)
if not cr_match:
    ko("inv17: STEP 6 CODE-REVIEW section not isolated")
else:
    cr = cr_match.group(1)
    if 'Skill("superpowers:requesting-code-review")' in cr:
        ok("inv17: CODE-REVIEW invokes Skill(\"superpowers:requesting-code-review\")")
    else:
        ko("inv17: CODE-REVIEW missing exact skill invocation")
    # Negative check: the non-existent skill name must not appear (silently no-ops if used).
    if 'Skill("superpowers:code-reviewer")' not in cr:
        ok("inv17: CODE-REVIEW does not reference the non-existent code-reviewer skill")
    else:
        ko("inv17: CODE-REVIEW references the non-existent 'superpowers:code-reviewer'")

report(passed, failed)
