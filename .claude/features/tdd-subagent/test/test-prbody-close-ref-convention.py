#!/usr/bin/env python3
"""Inv 64 — PR-body close-reference authoring convention.

The tdd-subagent's persistent guidance MUST embed a PR-body authoring
convention so a subagent never writes an enumeration that GitHub/merge
close-ref parsing mistakes for issue close-references:

  - PR bodies MUST NOT use `Fix #N` / `Fixes #N` / `Closes #N` for NON-issue
    enumeration (e.g. "Fix #1 / Fix #2 / Fix #3" for three sub-fixes) — those
    parse as issue references and can wrongly close issues #1/#2/#3.
  - Use plain enumeration instead: `Fix 1 / Fix 2 / Fix 3` or `Part 1/2/3`.
  - Reserve closing keywords for the ACTUAL target issue: exactly
    `Closes #<issue>`.

This complements #1101 (merge-prs.py cross-checks close-refs vs open-issue
state). Asserts the convention is present in BOTH the source and deployed
agent definitions and that the spec declares the matching invariant.
"""
import os

from _helpers import AGENT_PATH, REPO_ROOT, SPEC_PATH, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


DEPLOYED_AGENT = os.path.join(
    REPO_ROOT, ".claude", "agents", "rabbit-tdd-subagent.md"
)

# Tokens that, together, prove the convention is present. Each must appear in
# the guidance body. Grep-stable: keep these exact strings in lockstep with
# the agent-definition prose and the Inv 64 spec text.
REQUIRED_TOKENS = (
    "Fix #N",            # the forbidden enumeration form is named
    "Closes #<issue>",   # the reserved-for-target-issue form is named
    "enumeration",       # the convention is about non-issue enumeration
)


def read(path):
    with open(path) as f:
        return f.read()


for label, path in (("source agent", AGENT_PATH),
                    ("deployed agent", DEPLOYED_AGENT)):
    if not os.path.isfile(path):
        ko(f"{label} missing at {path}")
        continue
    text = read(path)
    missing = [t for t in REQUIRED_TOKENS if t not in text]
    if missing:
        ko(f"{label}: PR-body convention missing token(s): {missing}")
    else:
        ok(f"{label}: PR-body close-ref convention present")


# Spec must declare the invariant (Inv 64) capturing the convention.
spec = read(SPEC_PATH)
if "64." not in spec:
    ko("spec.md: Inv 64 (PR-body close-ref convention) not declared")
else:
    spec_missing = [t for t in REQUIRED_TOKENS if t not in spec]
    if spec_missing:
        ko(f"spec.md: Inv 64 missing token(s): {spec_missing}")
    else:
        ok("spec.md: Inv 64 declares the PR-body close-ref convention")


report(passed, failed)
