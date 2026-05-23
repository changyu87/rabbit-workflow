#!/usr/bin/env python3
"""Inv 14, 15, 16 — IMPLEMENT commit ordering, TEST-GREEN impl-SHA
capture, UNLOCK chore commit pattern."""
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

# Inv 14: IMPLEMENT step has the commit-inside-loop pattern with the
# correct conventional-commit verbs.
impl_match = re.search(r"STEP 6 — IMPLEMENT\n═+\n(.*?)\n═+\nSTEP 7", prompt, re.DOTALL)
if not impl_match:
    ko("inv14: STEP 6 IMPLEMENT section not isolated")
else:
    impl = impl_match.group(1)
    if re.search(r"git add \S+/?$", impl, re.MULTILINE) or "git add " in impl:
        ok("inv14: IMPLEMENT loop has `git add`")
    else:
        ko("inv14: IMPLEMENT loop missing `git add`")
    if 'fix(tdd-subagent):' in impl or 'fix(<feature>):' in impl:
        ok("inv14: IMPLEMENT loop has fix(<feature>): commit message")
    else:
        ko("inv14: IMPLEMENT loop missing fix(<feature>): commit message")
    if 'feat(' in impl:
        ok("inv14: IMPLEMENT loop documents feat() alternative")
    else:
        ko("inv14: IMPLEMENT loop missing feat() alternative")
    # Ordering: commit must appear BEFORE the impl transition call.
    commit_pos = impl.find("git commit")
    transition_pos = impl.find("transition")
    if 0 <= commit_pos < transition_pos:
        ok("inv14: commit precedes `tdd-step.py transition ... impl`")
    else:
        ko(f"inv14: commit ordering wrong (commit={commit_pos}, transition={transition_pos})")

# Inv 15: TEST-GREEN captures IMPL_SHA BEFORE writing tdd-report.
tg_match = re.search(r"STEP 8 — TEST-GREEN\n═+\n(.*?)\n═+\nSTEP 9", prompt, re.DOTALL)
if not tg_match:
    ko("inv15: STEP 8 TEST-GREEN section not isolated")
else:
    tg = tg_match.group(1)
    sha_pos = tg.find("IMPL_SHA=$(git rev-parse HEAD)")
    report_pos = tg.find("tdd-report-")
    if sha_pos >= 0 and report_pos > sha_pos:
        ok("inv15: TEST-GREEN captures IMPL_SHA before referencing tdd-report path")
    else:
        ko(f"inv15: IMPL_SHA capture ordering wrong (sha={sha_pos}, report={report_pos})")
    if '"impl_commit": "$IMPL_SHA"' in tg:
        ok("inv15: tdd-report JSON binds impl_commit to $IMPL_SHA")
    else:
        ko("inv15: tdd-report JSON does not bind impl_commit to $IMPL_SHA")

# Inv 16: UNLOCK chore commit has the documented pattern.
unlock_match = re.search(r"STEP 9 — UNLOCK\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
if not unlock_match:
    ko("inv16: STEP 9 UNLOCK section not isolated")
else:
    body = unlock_match.group(1)
    if 'chore(tdd-subagent): advance tdd_state to test-green' in body:
        ok("inv16: UNLOCK chore commit message matches pattern")
    else:
        ko("inv16: UNLOCK chore commit message missing or wrong")
    if 'git add ' in body and 'feature.json' in body:
        ok("inv16: UNLOCK adds feature.json before commit")
    else:
        ko("inv16: UNLOCK does not stage feature.json")

report(passed, failed)
