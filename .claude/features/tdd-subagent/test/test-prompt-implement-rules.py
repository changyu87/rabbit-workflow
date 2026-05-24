#!/usr/bin/env python3
"""Inv 11, 18 — SKILL.md routing rule and Read-before-Edit warning in
IMPLEMENT step."""
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

# Inv 11: SKILL.md routing rule names skill-creator and forbids direct Write/Edit.
if "SKILL.md ROUTING" in prompt and "skill-creator:skill-creator" in prompt:
    ok("inv11: SKILL.md routing rule names skill-creator")
else:
    ko("inv11: SKILL.md routing rule missing or wrong skill")
if "CONSTITUTION VIOLATION" in prompt:
    ok("inv11: SKILL.md routing rule frames direct-edit as violation")
else:
    ko("inv11: SKILL.md routing rule missing violation framing")

# Inv 18: Read-before-Edit warning.
if "Read it in this session first" in prompt:
    ok("inv18: Read-before-Edit warning present in IMPLEMENT")
else:
    ko("inv18: Read-before-Edit warning missing")

report(passed, failed)
