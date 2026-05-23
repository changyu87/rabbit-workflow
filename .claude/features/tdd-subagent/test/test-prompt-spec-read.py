#!/usr/bin/env python3
"""Inv 13 — SPEC-READ diffs against HEAD~1, not HEAD."""
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

# Inv 13: SPEC-READ section runs `git diff HEAD~1 -- <feature_dir>/docs/spec/`.
spec_read_match = re.search(r"STEP 1 — SPEC-READ\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
if not spec_read_match:
    ko("inv13: STEP 1 SPEC-READ section not isolated")
else:
    body = spec_read_match.group(1)
    if re.search(r"git diff HEAD~1 -- .*?/docs/spec/", body):
        ok("inv13: SPEC-READ runs `git diff HEAD~1 -- <feature_dir>/docs/spec/`")
    else:
        ko("inv13: SPEC-READ missing `git diff HEAD~1 ... docs/spec/`")
    if "git diff HEAD " not in body:
        ok("inv13: SPEC-READ does not use bare `git diff HEAD`")
    else:
        ko("inv13: SPEC-READ contains bare `git diff HEAD`")

report(passed, failed)
