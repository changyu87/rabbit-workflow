#!/usr/bin/env python3
"""test-spec-bodies-allowlist-rae-retired-literal.py — issue #556 (part b).

End-to-end test that the production ALLOWLIST in
test-spec-bodies-no-historical-tags.py exempts the legitimate literal
status-enum value "retired" in rabbit-auto-evolve's docs/spec.md.

rabbit-auto-evolve's spec.md documents triage-issue.py's verbatim
`status == "retired"` check (feature.json status enum, contract Inv 36) on
the Inv 22 triage decision-table row that reads
`Feature's `feature.json.status == "retired"`` -> `close-not-planned` /
`feature-retired`. The strict-tier checker flags the bare word "retired" as
tombstone language, but here it is the load-bearing literal value the triage
interpreter checks verbatim (plus the `feature-retired` reason code) — it
cannot be reworded without making the spec inaccurate. This is the single
remaining strict-tier hit blocking rae from opting into the strict tier
(the #556 housekeeping_clean opt-in). It mirrors both the contract OWN-spec
retired-enum precedent and the rabbit-config status-enum precedent (#634).

The test drives the REAL checker (no fixture features root) with
rabbit-auto-evolve simulated as opted-in to the strict tier via the
RABBIT_HISTORICAL_TAGS_CLEANED override (which REPLACES the
feature.json-derived opt-in set, so ONLY rabbit-auto-evolve is
strict-enforced and every other feature stays baseline-only — keeping the
run's pass/fail pinned to the rae "retired" line under test). The "retired"
occurrence is the single strict-tier match in rabbit-auto-evolve's doc
surfaces, so:

  - WITH the production ALLOWLIST entry the run PASSES against the real
    features root (proving the line-pinned entry suppresses the real
    occurrence).
  - WITHOUT a matching (line-pinned) entry the same line is a genuine
    strict-tier violation — simulated by reproducing the "retired" line at
    a DIFFERENT line number in a fixture features root so the line-pinned
    production allowlist entry cannot match it; that run FAILS, naming
    rabbit-auto-evolve (proving the suppression is the line-pinned entry,
    not an unrelated condition).

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")
CHECKER = os.path.join(TEST_DIR, "test-spec-bodies-no-historical-tags.py")

RAE_SPEC = os.path.join(
    FEATURES_ROOT, "rabbit-auto-evolve", "docs", "spec.md")

# The load-bearing literal value the triage interpreter checks verbatim.
# Match the triage decision-table row that names the status-enum value.
RETIRED_RE = re.compile(r'feature\.json\.status == "retired"')

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


def run(features_root, cleaned):
    """Run the checker with the given features root and a forced opt-in set.
    cleaned is passed as RABBIT_HISTORICAL_TAGS_CLEANED (REPLACES the
    feature.json-derived set)."""
    env = dict(os.environ)
    env["RABBIT_HISTORICAL_TAGS_FEATURES_ROOT"] = features_root
    env["RABBIT_HISTORICAL_TAGS_CLEANED"] = cleaned
    env.pop("RABBIT_HISTORICAL_TAGS_ALLOWLIST", None)
    return subprocess.run(
        ["python3", CHECKER], capture_output=True, text=True, env=env)


# t0: checker + rabbit-auto-evolve spec.md exist.
if not os.path.isfile(CHECKER):
    fail("t0", f"checker missing: {CHECKER}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
if not os.path.isfile(RAE_SPEC):
    fail("t0", f"rabbit-auto-evolve spec.md missing: {RAE_SPEC}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "checker and rabbit-auto-evolve spec.md exist")

# Locate the "retired" status-enum triage row in the live rae spec.md.
# The production ALLOWLIST entry is line-pinned to this number.
with open(RAE_SPEC) as f:
    rae_lines = f.readlines()
retired_lines = [
    i for i, ln in enumerate(rae_lines, start=1) if RETIRED_RE.search(ln)
]
if len(retired_lines) != 1:
    fail("t0b", f"expected exactly one triage 'retired' status-enum row in "
                f"{RAE_SPEC}; found {retired_lines}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
RETIRED_LINE = retired_lines[0]
ok("t0b", f"rabbit-auto-evolve 'retired' status-enum literal on line "
          f"{RETIRED_LINE}")

# t1: against the REAL features root with rabbit-auto-evolve opted in, the run
# PASSES — the production ALLOWLIST entry (line-pinned to RETIRED_LINE)
# suppresses the only strict-tier match in rae's doc surfaces.
r_real = run(FEATURES_ROOT, "rabbit-auto-evolve")
if r_real.returncode == 0:
    ok("t1", "production allowlist suppresses real rabbit-auto-evolve "
             "'retired' literal (opted-in run passes)")
else:
    fail("t1", "expected exit 0 against real features root with "
               "rabbit-auto-evolve opted in; "
               f"exit={r_real.returncode}; "
               f"stdout={r_real.stdout}; stderr={r_real.stderr}")

# t2: paired negative arm — reproduce rae's spec.md triage row in a fixture
# features root with the "retired" line shifted to a DIFFERENT line number
# so the line-pinned production allowlist entry cannot match it. The run
# MUST FAIL, naming rabbit-auto-evolve — proving the line is otherwise a
# genuine strict-tier violation and the suppression in t1 is the line-pinned
# entry, not an unrelated condition.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "rabbit-auto-evolve", "docs")
    os.makedirs(fdir, exist_ok=True)
    # Prepend blank lines so the triage row lands at a line number that is
    # NOT the pinned production allowlist line for rabbit-auto-evolve.
    shifted = ["\n"] * (RETIRED_LINE + 5) + [
        '   | 4 | Feature\'s `feature.json.status == "retired"` | '
        '`close-not-planned` | `feature-retired` |\n'
    ]
    with open(os.path.join(fdir, "spec.md"), "w") as f:
        f.writelines(shifted)
    r_shift = run(tmp, "rabbit-auto-evolve")
    out = r_shift.stdout + r_shift.stderr
    if r_shift.returncode != 0 and "rabbit-auto-evolve" in out:
        ok("t2", "unpinned 'retired' line is a genuine strict-tier violation")
    else:
        fail("t2", "expected nonzero + 'rabbit-auto-evolve' when 'retired' "
                   f"line is NOT at the pinned number; "
                   f"exit={r_shift.returncode}; "
                   f"stdout={r_shift.stdout}; stderr={r_shift.stderr}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-bodies-allowlist-rae-retired-literal: FAIL",
          file=sys.stderr)
    sys.exit(1)

print("test-spec-bodies-allowlist-rae-retired-literal: all checks passed.")
sys.exit(0)
