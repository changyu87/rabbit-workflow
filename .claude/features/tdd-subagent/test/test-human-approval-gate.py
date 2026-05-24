#!/usr/bin/env python3
"""Inv 25, 26 — --human-approval-gate true/false branches."""
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


def section(prompt, n, name):
    """Extract a single STEP <n> — <name> section body, or None."""
    m = re.search(
        rf"STEP {n} — {re.escape(name)}\n═+\n(.*?)\n═+\nSTEP {n + 1}",
        prompt,
        re.DOTALL,
    )
    return m.group(1) if m else None


# Inv 25: --human-approval-gate true (default) → full HUMAN-APPROVAL section.
res_true = run_dispatch("--human-approval-gate", "true")
body_true = section(res_true.stdout, 2, "HUMAN-APPROVAL")
if body_true and 'Skill("superpowers:writing-plans")' in body_true:
    ok("inv25: gate=true — HUMAN-APPROVAL invokes superpowers:writing-plans")
else:
    ko("inv25: gate=true — HUMAN-APPROVAL missing writing-plans invocation")
if body_true and "wait for explicit approval" in body_true:
    ok("inv25: gate=true — HUMAN-APPROVAL instructs subagent to wait for approval")
else:
    ko("inv25: gate=true — HUMAN-APPROVAL missing wait-for-approval instruction")

# Inv 25: default (no flag) matches gate=true.
res_default = run_dispatch()
body_default = section(res_default.stdout, 2, "HUMAN-APPROVAL")
if body_default is not None and body_default == body_true:
    ok("inv25: gate default matches --human-approval-gate true")
else:
    ko("inv25: gate default differs from --human-approval-gate true")

# Inv 26: --human-approval-gate false → stub.
res_false = run_dispatch("--human-approval-gate", "false")
body_false = section(res_false.stdout, 2, "HUMAN-APPROVAL")
if body_false and "Skipped" in body_false and "--human-approval-gate false" in body_false:
    ok("inv26: gate=false — HUMAN-APPROVAL is a 'Skipped' stub")
else:
    ko(f"inv26: gate=false — HUMAN-APPROVAL is not a stub: {body_false!r}")
if body_false and 'Skill("superpowers:writing-plans")' not in body_false:
    ok("inv26: gate=false — HUMAN-APPROVAL does NOT invoke writing-plans")
else:
    ko("inv26: gate=false — HUMAN-APPROVAL still invokes writing-plans")

report(passed, failed)
