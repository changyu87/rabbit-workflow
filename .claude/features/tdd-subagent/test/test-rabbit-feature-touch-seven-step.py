#!/usr/bin/env python3
# E2E test for tdd-subagent spec invariants 13, 14, 15:
#   13. rabbit-feature-touch SKILL.md describes a seven-step sequence with the
#       seven step names in order: Scope Resolution, Create Branch, Spec Authoring,
#       Human Approval, Dispatch TDD Subagents, Collect and Verify HANDOFFs,
#       PR / Hand Off. Both the overview heading and every step heading reflect
#       this numbering.
#   14. Step 4 (Human Approval) is a dispatcher-side gate that surfaces the
#       impl-suggestion summary (request, spec changes, affected files,
#       implementation approach) and waits for explicit user approval. The
#       rationale that subagents cannot pause mid-execution is documented.
#   15. Step 4 is bypassable only via --no-human-approval passed to
#       dispatch-tdd-subagent.py. Silent bypass is prohibited.
#
# Reads the built/deployed SKILL.md (the surface artifact downstream consumers
# see) and asserts the spec invariants hold.

import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR
).decode().strip()

SOURCE_SKILL = os.path.join(
    REPO_ROOT,
    '.claude/features/tdd-subagent/skills/rabbit-feature-touch/SKILL.md',
)
DEPLOYED_SKILL = os.path.join(
    REPO_ROOT, '.claude/skills/rabbit-feature-touch/SKILL.md'
)

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


def load_skill():
    # Per the spec the deployed copy is the surface; assert both exist and
    # match, then read the deployed copy.
    if not os.path.isfile(SOURCE_SKILL):
        ko(f"source SKILL.md missing: {SOURCE_SKILL}")
        sys.exit(1)
    if not os.path.isfile(DEPLOYED_SKILL):
        ko(f"deployed SKILL.md missing: {DEPLOYED_SKILL}")
        sys.exit(1)
    with open(SOURCE_SKILL) as f:
        src = f.read()
    with open(DEPLOYED_SKILL) as f:
        dep = f.read()
    if src != dep:
        ko("deployed SKILL.md differs from source")
        sys.exit(1)
    return dep


SKILL = load_skill()


# ---- Invariant 13: seven-step sequence with named steps in order -------------

EXPECTED_STEPS = [
    (1, "Scope Resolution"),
    (2, "Create Branch"),
    (3, "Spec Authoring"),
    (4, "Human Approval"),
    (5, "Dispatch TDD Subagents"),
    (6, "Collect and Verify HANDOFFs"),
    (7, "PR / Hand Off"),
]


def t_inv13_overview_heading_says_seven_step():
    # The overview heading must say "Seven-Step" (not "Six-Step").
    if re.search(r"Seven[- ]Step", SKILL):
        ok("inv13: overview heading says 'Seven-Step'")
    else:
        ko("inv13: overview heading does not say 'Seven-Step'")
    if re.search(r"Unified Six[- ]Step", SKILL):
        ko("inv13: overview heading still says 'Six-Step' (must be 'Seven-Step')")
    else:
        ok("inv13: overview heading does not say 'Six-Step'")


def t_inv13_seven_step_headings_in_order():
    # Find every "Step N — <title>" heading in order; assert exact match.
    found = re.findall(r"###\s+Step\s+(\d+)\s+[-—]\s+([^\n]+)", SKILL)
    # Normalise titles by stripping trailing whitespace
    found = [(int(n), title.strip()) for (n, title) in found]
    if found == EXPECTED_STEPS:
        ok("inv13: all seven step headings appear in the correct order with the correct titles")
    else:
        ko(f"inv13: step headings mismatch. expected={EXPECTED_STEPS} got={found}")


def t_inv13_no_step_8_heading():
    if re.search(r"###\s+Step\s+8\b", SKILL):
        ko("inv13: Step 8 heading present (must be exactly seven steps)")
    else:
        ok("inv13: no Step 8 heading")


# ---- Invariant 14: Step 4 is dispatcher-side, surfaces summary, waits --------


def _step_section(n):
    # Extract the body for `### Step <n> — ...` up to the next `### ` or end.
    pattern = rf"###\s+Step\s+{n}\s+[-—].*?(?=\n###\s+|\Z)"
    m = re.search(pattern, SKILL, re.DOTALL)
    return m.group(0) if m else ""


def t_inv14_step4_surfaces_four_summary_fields():
    body = _step_section(4)
    if not body:
        ko("inv14: Step 4 section not found")
        return
    # The spec says the dispatcher surfaces request, spec changes, affected
    # files, and implementation approach.
    required = [
        ("Request", r"\bRequest\s+summary\b"),
        ("Spec changes", r"\bSpec\s+changes\b"),
        ("Affected files", r"\bAffected\s+files\b"),
        ("Implementation approach", r"\bImplementation\s+approach\b"),
    ]
    missing = [name for (name, pat) in required if not re.search(pat, body, re.IGNORECASE)]
    if not missing:
        ok("inv14: Step 4 surfaces request / spec changes / affected files / impl approach")
    else:
        ko(f"inv14: Step 4 missing summary fields: {missing}")


def t_inv14_step4_waits_for_explicit_approval():
    body = _step_section(4)
    if not body:
        ko("inv14: Step 4 section not found")
        return
    # Must say it waits for explicit approval.
    if re.search(r"explicit\s+(user\s+)?approval|wait\s+for\s+.*approval", body, re.IGNORECASE):
        ok("inv14: Step 4 waits for explicit user approval")
    else:
        ko("inv14: Step 4 does not document waiting for explicit user approval")


def t_inv14_step4_rationale_subagents_cannot_pause():
    body = _step_section(4)
    if not body:
        ko("inv14: Step 4 section not found")
        return
    # The dispatcher-side rationale: subagents run to completion / cannot
    # pause for user input.
    if re.search(r"cannot\s+pause|run\s+to\s+completion", body, re.IGNORECASE):
        ok("inv14: Step 4 documents rationale that subagents cannot pause / run to completion")
    else:
        ko("inv14: Step 4 missing rationale about subagents being unable to pause mid-execution")


# ---- Invariant 15: bypass only via --no-human-approval, no silent bypass ----


def t_inv15_step4_documents_bypass_flag():
    body = _step_section(4)
    if not body:
        ko("inv15: Step 4 section not found")
        return
    if "--no-human-approval" in body:
        ok("inv15: Step 4 documents --no-human-approval bypass flag")
    else:
        ko("inv15: Step 4 does not mention --no-human-approval bypass flag")


def t_inv15_step4_prohibits_silent_bypass():
    body = _step_section(4)
    if not body:
        ko("inv15: Step 4 section not found")
        return
    # Spec Inv 15 (v1.8.0): bypass authorization is the
    # .rabbit-human-approval-bypass marker file; in-conversation
    # acknowledgements alone are not sufficient. The SKILL.md must encode
    # the marker as the sole authorization mechanism (silent bypass via
    # phrase alone is prohibited).
    if (".rabbit-human-approval-bypass" in body
            and re.search(r"sole authorization|NOT sufficient|system of record", body)):
        ok("inv15: Step 4 prohibits silent bypass / requires marker authorization")
    else:
        ko("inv15: Step 4 does not prohibit silent bypass")


def t_inv15_step5_dispatch_template_lists_optional_flag():
    body = _step_section(5)
    if not body:
        ko("inv15: Step 5 section not found")
        return
    # The dispatch command template must list [--no-human-approval] as an
    # optional flag.
    if re.search(r"\[\s*--no-human-approval\s*\]", body):
        ok("inv15: Step 5 dispatch template lists [--no-human-approval] as optional flag")
    else:
        ko("inv15: Step 5 dispatch template does not list [--no-human-approval] as optional flag")


# ---- Run -------------------------------------------------------------------

print("running rabbit-feature-touch seven-step / human-approval tests")
t_inv13_overview_heading_says_seven_step()
t_inv13_seven_step_headings_in_order()
t_inv13_no_step_8_heading()
t_inv14_step4_surfaces_four_summary_fields()
t_inv14_step4_waits_for_explicit_approval()
t_inv14_step4_rationale_subagents_cannot_pause()
t_inv15_step4_documents_bypass_flag()
t_inv15_step4_prohibits_silent_bypass()
t_inv15_step5_dispatch_template_lists_optional_flag()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
