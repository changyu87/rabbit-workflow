#!/usr/bin/env python3
"""test-reduction-single-tdd.py — integration guard for #1189.

Locks in that a measured reduction wave's per-feature spec reduction rides a
SINGLE governed RED->GREEN cycle on the subagent's branch, with no dispatcher
pre-edit/pre-commit of the spec and no forced `--spec-no-change-reason` escape
hatch. The substantive behavior is delivered transitively by rabbit-feature-
touch's reduction/intent path (#1198), which DETECTS the wave from the request
signal rabbit-housekeep sends. This test pins the contract from the housekeep
side so the wiring cannot silently regress:

  t0: SIGNAL MATCH — rabbit-housekeep dispatches rabbit-feature-touch with the
      EXACT reduction signal `housekeep: measured reduction wave` that
      feature-touch's `is-reduction-wave` detection keys on. A drift in either
      phrase would silently fall back to the default (pre-commit) spec path.

  t1: NO STALE WORKAROUND — none of the housekeep doc/skill surfaces reference
      the old pre-commit-spec + `--spec-no-change-reason` escape hatch. The
      reduction wave authors the spec reduction INSIDE the subagent's single
      cycle; the workaround must not be reintroduced here.

  t2: SINGLE-TDD FRAMING DOCUMENTED — the SKILL.md Step-6 dispatch prose states
      that the spec reduction now rides ONE governed TDD cycle (the subagent
      authors the spec reduction and its gating test together). This is the
      honest #1189 acknowledgment on the housekeep surface.

Non-interactive. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SKILL = os.path.join(FEATURE_DIR, "skills", "rabbit-housekeep", "SKILL.md")
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")
CONTRACT = os.path.join(FEATURE_DIR, "docs", "contract.md")
COMMAND = os.path.join(FEATURE_DIR, "commands", "rabbit-housekeep.md")
DOC_SURFACES = [SKILL, SPEC, CONTRACT, COMMAND]

# The exact reduction signal feature-touch's is-reduction-wave detection keys
# on (rabbit-feature feature-touch.py `_REDUCTION_SIGNAL`, #1198). Matched as a
# case-insensitive substring there; rabbit-housekeep MUST emit it verbatim.
REDUCTION_SIGNAL = "housekeep: measured reduction wave"

# Tokens from the retired pre-commit + escape-hatch spec path. None must appear
# on a housekeep surface: the reduction wave does NOT pre-commit the spec.
WORKAROUND_TOKENS = ["--spec-no-change-reason", "spec-no-change-reason"]

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


with open(SKILL, encoding="utf-8") as f:
    skill = f.read()

# t0: the dispatch sends the exact reduction signal feature-touch detects.
dispatch = re.search(
    r'Skill\(\s*"rabbit-feature-touch"\s*,\s*args:\s*"([^"]*)"\s*\)', skill
)
if not dispatch:
    fail("t0", "no rabbit-feature-touch dispatch found in SKILL.md")
elif REDUCTION_SIGNAL not in dispatch.group(1).lower():
    fail("t0", f"dispatch args missing reduction signal: {dispatch.group(1)!r}")
else:
    ok("t0", f"dispatch carries the reduction signal {REDUCTION_SIGNAL!r}")

# t1: no stale pre-commit/escape-hatch workaround on any housekeep surface.
offenders = []
for p in DOC_SURFACES:
    with open(p, encoding="utf-8") as f:
        body = f.read()
    for tok in WORKAROUND_TOKENS:
        if tok in body:
            offenders.append(f"{os.path.basename(p)}:{tok}")
if offenders:
    fail("t1", f"stale pre-commit/escape-hatch workaround referenced: {offenders}")
else:
    ok("t1", "no --spec-no-change-reason / pre-commit-spec workaround referenced")

# t2: the single governed TDD cycle for the spec reduction is documented in the
# Step-6 dispatch prose (the honest #1189 acknowledgment).
SINGLE_TDD_MARKERS = ["single", "spec reduction"]
missing = [m for m in SINGLE_TDD_MARKERS if m.lower() not in skill.lower()]
if missing:
    fail("t2", f"single-TDD spec-reduction framing not documented: missing {missing}")
else:
    ok("t2", "Step-6 documents the single governed TDD cycle for the spec reduction")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
