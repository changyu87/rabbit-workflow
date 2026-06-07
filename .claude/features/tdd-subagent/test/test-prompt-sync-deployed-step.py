#!/usr/bin/env python3
"""Inv 46 — STEP 5 SYNC-DEPLOYED publish-sync semantics.

Reads the dispatched-subagent template at
.claude/features/contract/templates/prompts/tdd-subagent.txt and asserts:
  (i)   STEP 5 section header is `SYNC-DEPLOYED`.
  (ii)  Step body names `publish_file`, `publish_hook`, `publish_skill`,
        and `publish_settings` explicitly.
  (iii) Step body instructs `git add` of deployed paths AND a single
        atomic commit at end-of-step (`fix|feat(<feature>): <summary>`).
  (iv)  Step body instructs `tdd-step.py transition <feature_dir>
        sync-deployed` AFTER the commit.
  (v)   Step body specifies the fail-HANDOFF shape on publish failure
        with `tdd_state: impl`.

The template lives under contract per contract Inv 57; this feature's
TDD subagent does not own the template edit (the contract subagent
amends it in the sibling cycle).
"""
import os
import re
import sys

from _helpers import REPO_ROOT, report

TEMPLATE_PATH = os.path.join(
    REPO_ROOT,
    ".claude", "features", "contract", "templates", "prompts",
    "tdd-subagent.txt",
)

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


if not os.path.isfile(TEMPLATE_PATH):
    print(f"FATAL: template not found at {TEMPLATE_PATH}")
    sys.exit(1)

with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = f.read()

# Isolate the STEP 5 section (between STEP 5 banner and STEP 6 banner).
step5_match = re.search(r"STEP 5 — SYNC-DEPLOYED", template)
step6_match = re.search(r"STEP 6 —", template)
if not step5_match:
    ko("inv46.i: STEP 5 banner missing or not labelled SYNC-DEPLOYED")
    report(passed, failed)
if not step6_match:
    ko("inv46.i: STEP 6 banner missing — cannot isolate STEP 5 region")
    report(passed, failed)

# (i) header confirmed by the search above.
ok("inv46.i: STEP 5 section header is SYNC-DEPLOYED")

step5_region = template[step5_match.start():step6_match.start()]

# (ii) all four publish API names appear in the body.
for api in ("publish_file", "publish_hook", "publish_skill", "publish_settings"):
    if api in step5_region:
        ok(f"inv46.ii: STEP 5 body names {api}")
    else:
        ko(f"inv46.ii: STEP 5 body does not name {api}")

# (iii) git add + atomic commit at end-of-step.
if "git add" in step5_region:
    ok("inv46.iii: STEP 5 body instructs `git add` of deployed paths")
else:
    ko("inv46.iii: STEP 5 body missing `git add` instruction")

# Single atomic commit with fix|feat(<feature>): <summary> pattern.
# The template uses {{feature_name}} placeholder — accept either the
# placeholder form or a literal `fix(<feature>):`/`feat(<feature>):` form.
commit_pattern = re.search(
    r"git commit -m \"(fix|feat)\(\{?\{?(feature_name|<feature>)\}?\}?\):",
    step5_region,
)
if commit_pattern:
    ok("inv46.iii: STEP 5 body has atomic commit `fix|feat(<feature>): <summary>`")
else:
    ko("inv46.iii: STEP 5 body missing atomic commit instruction")

# (iv) transition into sync-deployed AFTER the commit.
commit_pos = step5_region.find("git commit")
trans_pos = step5_region.find("sync-deployed")
# The string "sync-deployed" can appear in prose; require it appears with the
# tdd-step.py transition invocation specifically.
trans_inv_match = re.search(
    r"(?:tdd-step\.py|\{\{tdd_step_py\}\}).*?transition\s+\S+\s+sync-deployed",
    step5_region,
    re.DOTALL,
)
trans_inv_pos = trans_inv_match.start() if trans_inv_match else -1
if commit_pos >= 0 and trans_inv_pos > commit_pos:
    ok("inv46.iv: STEP 5 body instructs `tdd-step.py transition <dir> sync-deployed` AFTER commit")
else:
    ko(
        f"inv46.iv: STEP 5 transition-into-sync-deployed not after commit "
        f"(commit={commit_pos}, transition={trans_inv_pos})"
    )

# (v) fail-HANDOFF shape on publish failure with tdd_state: impl.
# The fail-handoff body must mention publish failure, tdd_state: impl, and
# test_result: not_run somewhere in the STEP 5 section.
fail_signals = [
    "tdd_state: impl",
    "test_result: not_run",
    "spec_compliance: fail",
]
missing = [s for s in fail_signals if s not in step5_region]
if not missing:
    ok("inv46.v: STEP 5 body specifies fail-HANDOFF (tdd_state: impl, test_result: not_run, spec_compliance: fail)")
else:
    ko(f"inv46.v: STEP 5 fail-HANDOFF missing fields: {missing}")

# The fail-HANDOFF must also reference a SYNC-DEPLOYED-specific notes
# string mentioning the publish failure source.
if re.search(r"SYNC-DEPLOYED failed", step5_region):
    ok("inv46.v: STEP 5 fail-HANDOFF notes mention 'SYNC-DEPLOYED failed'")
else:
    ko("inv46.v: STEP 5 fail-HANDOFF missing 'SYNC-DEPLOYED failed' notes substring")

report(passed, failed)
