#!/usr/bin/env python3
"""test-spec-install-smoke-invariant.py — rabbit-auto-evolve Inv 63 (issue #966).

The pre-merge install smoke gate: the merge phase runs an isolated, network-
free fresh-install + update smoke of rabbit-cage's install.py against the
current tree, so install/closure breakage (fresh-install `source not found`
aborts, `--update` closure-shrink failures) is caught BEFORE a PR merges. A
non-zero smoke exit fails the merge phase, blocking the batch.

The originating issue's "Inv 66" reflects the contract feature's invariant
namespace; this feature's `## Invariants` section is locally numbered, so the
gate lands as the next contiguous local invariant (Inv 63). Inside
safety-check.py's bottom-line table it is local check 6.

This is the end-to-end spec regression. It asserts:
  1. spec.md carries the Inv 63 install-smoke text (install-smoke.py, the
     merge-phase gating, the block-the-merge semantics).
  2. contract.md declares the rabbit-cage install.py INVOKE.
  3. safety-check.py enforces the smoke (check 6) in the merge phase (the
     install smoke is wired into INV_BY_PHASE['merge']).
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
CONTRACT_MD = FEATURE_DIR / "docs" / "contract.md"
SAFETY_CHECK = FEATURE_DIR / "scripts" / "safety-check.py"
SMOKE = FEATURE_DIR / "scripts" / "install-smoke.py"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) spec.md carries Inv 66 ----------------------------------------
spec = norm(SPEC_MD.read_text())
spec_low = spec.lower()

SPEC_REQUIRED = [
    "install-smoke.py",
    "install smoke",
    "merge",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing install-smoke phrase(s): {missing!r}")
else:
    ok("spec.md carries the pre-merge install-smoke invariant (Inv 66)")

if re.search(r"inv(ariant)?\s*63", spec_low):
    ok("spec.md references Inv 63")
else:
    fail("spec.md does not reference Inv 63")


# --- (2) contract.md declares the install.py INVOKE --------------------
contract = norm(CONTRACT_MD.read_text())
contract_low = contract.lower()
if "rabbit-cage/install.py" in contract_low:
    ok("contract.md declares the rabbit-cage install.py invoke")
else:
    fail("contract.md does not declare the rabbit-cage install.py invoke")


# --- (3) safety-check.py wires the smoke into the merge phase -----------
sc = SAFETY_CHECK.read_text()
sc_norm = norm(sc)
if "install-smoke.py" in sc_norm or "install_smoke" in sc_norm.lower():
    ok("safety-check.py references the install smoke")
else:
    fail("safety-check.py does not reference the install smoke")

# The merge phase bottom-line check list must include the install smoke (6).
m = re.search(r"\"merge\"\s*:\s*\[([^\]]*)\]", sc)
if not m:
    fail("safety-check.py: could not find the merge phase invariant list")
else:
    nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
    if 6 in nums:
        ok("safety-check.py: merge phase enforces the install smoke (check 6)")
    else:
        fail(f"safety-check.py: merge phase list {nums} does not include 6")

if not SMOKE.is_file():
    fail(f"install-smoke.py not found at {SMOKE}")
else:
    ok("install-smoke.py exists in scripts/")


sys.exit(FAIL)
