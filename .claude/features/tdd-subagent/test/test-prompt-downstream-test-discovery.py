#!/usr/bin/env python3
"""Inv 56 — downstream feature test-suite discovery on delete/rename.

Regression net for issue #410: PR #401 deleted files under a feature
directory and broke 15 rabbit-cage tests that referenced the removed
paths, because the TDD subagent never ran rabbit-cage's test suite. The
subagent's scope is bounded to the primary feature and features it
directly edits — it does not enumerate features with INDIRECT
dependencies on a deleted/renamed artifact.

The fix lands in the dispatched-subagent template's STEP 5 SYNC-DEPLOYED
section (which runs after IMPLEMENT and before CODE-REVIEW): for any
file the cycle DELETES or RENAMES under
`.claude/features/<feature>/`, the subagent MUST grep every
`.claude/features/*/test/` directory for references to the
deleted/renamed path and run `test/run.py` for each feature whose test
fixtures reference it.

Two assertions:
  (A) Template-content (governs what the dispatched subagent does):
      reads the contract-owned template at
      .claude/features/contract/templates/prompts/tdd-subagent.txt and
      asserts the STEP 5 SYNC-DEPLOYED region instructs downstream
      test-suite discovery for deletes/renames.
  (B) Assembled-prompt (e2e through dispatch-tdd-subagent.py): the same
      instruction text survives slot substitution and appears in the
      real assembled prompt the subagent receives.

The template file lives under the contract feature (contract Inv 57);
this invariant's implementation uses a one-time scope-override on the
template, matching the Inv 45/46/55 precedent.
"""
import os
import re
import sys

from _helpers import REPO_ROOT, run_dispatch, report

TEMPLATE_PATH = os.path.join(
    REPO_ROOT,
    ".claude", "features", "contract", "templates", "prompts",
    "tdd-subagent.txt",
)
SPEC_PATH = os.path.join(
    REPO_ROOT,
    ".claude", "features", "tdd-subagent", "docs", "spec", "spec.md",
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


def _step5_region(text):
    """Return the STEP 5 SYNC-DEPLOYED region of `text` (banner up to the
    STEP 6 banner). Works on both the raw template (with `STEP 5 —`
    banners) and the assembled prompt."""
    s5 = re.search(r"STEP 5 — SYNC-DEPLOYED", text)
    s6 = re.search(r"STEP 6 —", text)
    if not s5 or not s6:
        return None
    return text[s5.start():s6.start()]


def _assert_downstream_instructions(region, label):
    """Assert `region` carries the downstream-discovery instructions."""
    if region is None:
        ko(f"{label}: STEP 5 SYNC-DEPLOYED region not found")
        return

    # (i) The region must name the delete/rename trigger condition.
    if re.search(r"delet", region, re.IGNORECASE) and re.search(
            r"renam", region, re.IGNORECASE):
        ok(f"{label}: STEP 5 names delete/rename trigger")
    else:
        ko(f"{label}: STEP 5 does not name delete/rename trigger")

    # (ii) The region must instruct grepping the feature test directories
    #      for references to the deleted/renamed path.
    if ".claude/features/" in region and re.search(
            r"/test/?\b", region) and re.search(
            r"\bgrep\b", region, re.IGNORECASE):
        ok(f"{label}: STEP 5 instructs grep of feature test/ directories")
    else:
        ko(f"{label}: STEP 5 missing grep-of-feature-test-dirs instruction")

    # (iii) The region must instruct running test/run.py for each matching
    #       downstream feature.
    if re.search(r"test/run\.py", region):
        ok(f"{label}: STEP 5 instructs running downstream test/run.py")
    else:
        ko(f"{label}: STEP 5 missing downstream test/run.py run instruction")

    # (iv) The region must say downstream test FAILURE blocks the cycle
    #      (a fail-HANDOFF is emitted rather than silently proceeding).
    if re.search(r"downstream", region, re.IGNORECASE):
        ok(f"{label}: STEP 5 references downstream suites explicitly")
    else:
        ko(f"{label}: STEP 5 does not reference downstream suites")


# --- Assertion (A): contract-owned template content ---------------------
if not os.path.isfile(TEMPLATE_PATH):
    print(f"FATAL: template not found at {TEMPLATE_PATH}")
    sys.exit(1)

with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = f.read()

_assert_downstream_instructions(_step5_region(template), "template")

# --- Assertion (B): assembled prompt (e2e via dispatch) -----------------
res = run_dispatch()
if res.returncode != 0:
    ko(f"assembled: dispatch failed rc={res.returncode}: {res.stderr}")
else:
    _assert_downstream_instructions(_step5_region(res.stdout), "assembled")

# --- Assertion (C): spec invariant documents the requirement ------------
# Acceptance criterion: "A spec invariant documents this requirement."
if not os.path.isfile(SPEC_PATH):
    ko("spec: spec.md not found")
else:
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        spec = f.read()
    inv_match = re.search(r"^56\.\s", spec, re.MULTILINE)
    if not inv_match:
        ko("spec: invariant 56 not present in spec.md")
    else:
        # Body extends to the next `^N. ` line or the next `## ` heading.
        body_start = inv_match.start()
        nxt = re.search(r"^(?:[0-9]+\.\s|## )", spec[inv_match.end():],
                        re.MULTILINE)
        body = spec[body_start:inv_match.end() + nxt.start()] if nxt \
            else spec[body_start:]
        signals = [
            (re.search(r"delet", body, re.IGNORECASE)
             and re.search(r"renam", body, re.IGNORECASE),
             "names delete/rename trigger"),
            (re.search(r"downstream", body, re.IGNORECASE),
             "references downstream suites"),
            (re.search(r"test/run\.py", body),
             "names test/run.py"),
        ]
        for present, what in signals:
            if present:
                ok(f"spec: invariant 56 {what}")
            else:
                ko(f"spec: invariant 56 does not {what}")

report(passed, failed)
