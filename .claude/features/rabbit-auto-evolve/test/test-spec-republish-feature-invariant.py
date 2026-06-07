#!/usr/bin/env python3
"""test-spec-republish-feature-invariant.py — rabbit-auto-evolve Inv 55 (#562).

Asserts that docs/spec.md, docs/contract.md, and skills/.../SKILL.md document
and declare the deterministic deployed-surface republish step:

  1. spec.md carries Inv 55 naming the republish script, the
     scope-guard-denied deployed-copy problem, the contract.lib.publish
     cross-scope invoke, idempotency / JSON-summary / no-manifest no-op, and
     the dispatcher pre-PR sequencing.
  2. contract.md `invokes.modules` declares the cross-scope
     contract.lib.publish call (rabbit-auto-evolve does not edit the contract
     feature).
  3. SKILL.md documents the post-handoff dispatcher step that invokes
     republish-feature.py before opening the PR (script-tier, no inline python).

This is the spec-level regression guarding the republish contract; the
behavioral e2e lives in test-republish-feature.py.
"""

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
CONTRACT_MD = FEATURE_DIR / "docs" / "contract.md"
SKILL_MD = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) spec.md carries the republish invariant ------------------------
# (number not pinned: the #751 deep slim reflowed the numbering.)
spec_low = norm(SPEC_MD.read_text()).lower()

SPEC_REQUIRED = [
    "deployed-surface republish",
    "republish-feature.py",
    "contract.lib.publish",
    "test-deployed-skills-match-source.py",
    "manifest",
    "idempotent",
    "before opening the pr",
]
missing = [s for s in SPEC_REQUIRED if s not in spec_low]
if missing:
    fail(f"spec.md missing republish-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the republish invariant with the republish script, the "
       "publish invoke, the deployed-skills test, idempotency, and pre-PR "
       "sequencing")

# The scope-guard-denied deployed-copy problem must be documented.
if "scope" in spec_low and ("deployed" in spec_low):
    ok("spec.md documents the scope-guard-denied deployed-copy problem")
else:
    fail("spec.md does not document the scope-guard / deployed-copy problem")

# A feature with no manifest must be documented as a clean no-op.
if "no manifest" in spec_low and "no-op" in spec_low:
    ok("spec.md documents the no-manifest clean no-op")
else:
    fail("spec.md does not document the no-manifest clean no-op")

# --- (2) contract.md invokes.modules declares the publish call ----------
contract_text = CONTRACT_MD.read_text()
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
        modules = obj.get("invokes", {}).get("modules", [])
        publish = [d for d in modules if isinstance(d, dict)
                   and "contract/lib/publish.py" in d.get("path", "")]
        if publish:
            ok("contract.md invokes.modules declares contract.lib.publish")
        else:
            fail("contract.md invokes.modules missing the contract.lib.publish "
                 f"cross-scope invoke: {modules!r}")

# --- (3) SKILL.md documents the pre-PR republish step -------------------
skill_text = SKILL_MD.read_text()
skill_low = norm(skill_text).lower()
if "republish-feature.py" not in skill_low:
    fail("SKILL.md does not mention republish-feature.py")
elif "before" not in skill_low or "pr" not in skill_low:
    fail("SKILL.md does not document running republish before opening the PR")
else:
    ok("SKILL.md documents invoking republish-feature.py before opening the PR")

# Script-tier: SKILL.md must invoke the script, not carry inline python that
# walks the manifest itself. Guard against an inline publish call or a Python
# import of the publish lib sneaking into the SKILL body (prose describing the
# script reading the manifest is fine).
if re.search(r"contract\.lib\.publish\s*\.\w+\s*\(", skill_text) or \
        re.search(r"\bfrom\s+lib\s+import\s+publish\b", skill_text) or \
        re.search(r"\bimport\s+publish\b", skill_text):
    fail("SKILL.md appears to inline the publish call (should be script-tier)")
else:
    ok("SKILL.md keeps the republish step script-tier (no inline publish call)")

print()
sys.exit(FAIL)
