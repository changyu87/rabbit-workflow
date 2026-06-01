#!/usr/bin/env python3
"""Inv 14, 15, 16 — IMPLEMENT staging (no commit), TEST-GREEN impl-SHA
capture, UNLOCK chore commit pattern (8-step layout: STEP 7 TEST-GREEN,
STEP 8 UNLOCK; commit now happens at end of SYNC-DEPLOYED, not IMPLEMENT)."""
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

# Inv 14 (amended): IMPLEMENT step stages with `git add` and runs the
# `tdd-step.py transition ... impl` call at end-of-step — but DEFERS the
# commit until SYNC-DEPLOYED.
impl_match = re.search(r"STEP 4 — IMPLEMENT\n═+\n(.*?)\n═+\nSTEP 5", prompt, re.DOTALL)
if not impl_match:
    ko("inv14: STEP 4 IMPLEMENT section not isolated")
else:
    impl = impl_match.group(1)
    if re.search(r"git add \S+/?$", impl, re.MULTILINE) or "git add " in impl:
        ok("inv14: IMPLEMENT loop has `git add`")
    else:
        ko("inv14: IMPLEMENT loop missing `git add`")
    # Inv 14 (amended): IMPLEMENT must NOT contain the atomic commit — that
    # was moved into SYNC-DEPLOYED. Stating the deferral explicitly is the
    # spec's intent ("DEFER the commit until the end of SYNC-DEPLOYED").
    if re.search(r"defer", impl, re.IGNORECASE):
        ok("inv14: IMPLEMENT documents the deferred-commit handoff to SYNC-DEPLOYED")
    else:
        ko("inv14: IMPLEMENT missing explicit deferred-commit note")
    # tdd-step.py transition into impl must appear in IMPLEMENT (the state
    # advance for `code written` happens here per Inv 14 amended).
    if re.search(r"tdd-step\.py.*?transition\s+\S+\s+impl", impl, re.DOTALL):
        ok("inv14: IMPLEMENT runs `tdd-step.py transition <dir> impl`")
    else:
        ko("inv14: IMPLEMENT missing tdd-step.py transition into impl")

# Inv 14 (amended) — SYNC-DEPLOYED step contains the single atomic
# commit covering BOTH feature-local staged changes and deployed-copy sync.
sync_match = re.search(r"STEP 5 — SYNC-DEPLOYED\n═+\n(.*?)\n═+\nSTEP 6", prompt, re.DOTALL)
if not sync_match:
    ko("inv14: STEP 5 SYNC-DEPLOYED section not isolated")
else:
    sync = sync_match.group(1)
    if 'fix(tdd-subagent):' in sync or 'fix(<feature>):' in sync or re.search(r'fix\(\S+\):', sync):
        ok("inv14: SYNC-DEPLOYED contains the atomic fix(<feature>): commit")
    else:
        ko("inv14: SYNC-DEPLOYED missing atomic commit message")
    if 'feat(' in sync:
        ok("inv14: SYNC-DEPLOYED documents feat() alternative")
    else:
        ko("inv14: SYNC-DEPLOYED missing feat() alternative")

# Inv 15: TEST-GREEN (now STEP 7) captures IMPL_SHA BEFORE writing tdd-report.
tg_match = re.search(r"STEP 7 — TEST-GREEN\n═+\n(.*?)\n═+\nSTEP 8", prompt, re.DOTALL)
if not tg_match:
    ko("inv15: STEP 7 TEST-GREEN section not isolated")
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

# Inv 16: UNLOCK (now STEP 8) chore commit has the documented pattern.
unlock_match = re.search(r"STEP 8 — UNLOCK\n═+\n(.*?)\n═+\n", prompt, re.DOTALL)
if not unlock_match:
    ko("inv16: STEP 8 UNLOCK section not isolated")
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
