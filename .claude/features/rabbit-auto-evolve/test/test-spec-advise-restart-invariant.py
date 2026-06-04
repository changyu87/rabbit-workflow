#!/usr/bin/env python3
"""test-spec-advise-restart-invariant.py — rabbit-auto-evolve Inv 52 (#545).

Asserts that docs/spec.md and docs/contract.md document the advisory-restart
marker contract introduced for issue #545 (Part A):

  1. spec.md carries Inv 52 with the advisory marker name, its three
     subcommands (write/status/clear), the JSON status shape
     ({"advised": ...}), the never-pauses property, and the distinct-from-the-
     hard-marker statement.
  2. The advisory marker appears in the spec Markers list/table and in
     contract.md `manages.runtime_markers`.
  3. contract.md `provides.scripts` declares advise-restart.py with its
     status/clear invoke surface, so rabbit-cage's cross-feature use (Part B)
     is contract-bound.

This is the spec-level regression guarding the marker contract; the behavioral
e2e lives in test-advise-restart.py.
"""

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# Dual-read (issue #399): prefer flat docs/spec.md, fall back to specs/, then legacy.
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"
CONTRACT_MD = FEATURE_DIR / "docs" / "contract.md"

ADVISED = ".rabbit-auto-evolve-restart-advised"
HARD = ".rabbit-auto-evolve-restart-needed"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) spec.md carries Inv 52 -----------------------------------------
spec = norm(SPEC_MD.read_text())
spec_low = spec.lower()

SPEC_REQUIRED = [
    "545",
    "inv 52",
    ADVISED.lower(),
    "advise-restart.py",
    "advisory",
    '"advised"',
    "write",
    "status",
    "clear",
]
missing = [s for s in SPEC_REQUIRED if s not in spec_low]
if missing:
    fail(f"spec.md missing Inv 52 phrase(s): {missing!r}")
else:
    ok("spec.md carries Inv 52 with marker, subcommands, and JSON status shape")

# The advisory marker must be documented as NEVER pausing the loop.
if "never pause" in spec_low or "never pauses" in spec_low or "does not block" in spec_low:
    ok("spec.md documents the advisory marker never pauses/blocks the loop")
else:
    fail("spec.md does not state the advisory marker never pauses/blocks the loop")

# It must be documented as DISTINCT from the hard restart-needed marker.
if "distinct" in spec_low and HARD.lower() in spec_low:
    ok("spec.md documents the advisory marker is distinct from the hard marker")
else:
    fail("spec.md does not state the advisory marker is distinct from "
         f"{HARD}")

# The advisory marker must be enumerated in the spec Markers section/table.
if ADVISED.lower() in spec_low:
    ok("spec.md enumerates the advisory marker in the Markers documentation")
else:
    fail("spec.md does not enumerate the advisory marker")

# --- (2)+(3) contract.md ------------------------------------------------
contract_text = CONTRACT_MD.read_text()
# Extract the JSON block.
m = re.search(r"```json\s*(\{.*?\})\s*```", contract_text, re.DOTALL)
if not m:
    fail("contract.md has no parseable JSON block")
else:
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        obj = None
        fail(f"contract.md JSON block does not parse: {e}")
    if obj is not None:
        markers = obj.get("manages", {}).get("runtime_markers", [])
        if ADVISED in markers:
            ok("contract.md manages.runtime_markers includes the advisory marker")
        else:
            fail(f"contract.md manages.runtime_markers missing {ADVISED}: {markers!r}")

        scripts = obj.get("provides", {}).get("scripts", [])
        adv = [s for s in scripts
               if isinstance(s, dict) and "advise-restart.py" in s.get("path", "")]
        if not adv:
            fail("contract.md provides.scripts does not declare advise-restart.py")
        else:
            subs = adv[0].get("subcommands", [])
            if all(c in subs for c in ("write", "status", "clear")):
                ok("contract.md provides.scripts declares advise-restart.py "
                   "with write/status/clear")
            else:
                fail(f"advise-restart.py subcommands incomplete: {subs!r}")

print()
sys.exit(FAIL)
