#!/usr/bin/env python3
"""test-spec-clean-dispatch-leaks-invariant.py — rabbit-auto-evolve Inv 43
(issue #583): deterministic pre-merge cleanup of known worktree-dispatch leaks.

This e2e regression asserts:

  1. The spec carries the Inv 43 text (issue #583 cross-ref, the
     `clean-dispatch-leaks.py` script, the two leak classes —
     `.rabbit-scope-active-*` markers and bookkeeping-only feature.json — the
     run BEFORE merge, and the fail-loudly-on-unexpected-dirt safety property).
  2. The source SKILL.md documents the pre-merge cleanup step.
  3. All four versioned artifacts (feature.json, spec.md, contract.md, source
     SKILL.md frontmatter) are bumped in lockstep to the SAME version (Inv 15).

The DEPLOYED SKILL.md copy is intentionally NOT asserted here: the dispatcher
republishes it after the feature touch, so this test stays green pre-republish.
"""

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]


def _resolve_doc(name):
    for candidate in (
        FEATURE_DIR / "docs" / name,
        FEATURE_DIR / "specs" / name,
        FEATURE_DIR / "docs" / "spec" / name,
    ):
        if candidate.is_file():
            return candidate
    return FEATURE_DIR / "docs" / name


SPEC_MD = _resolve_doc("spec.md")
CONTRACT_MD = _resolve_doc("contract.md")
FEATURE_JSON = FEATURE_DIR / "feature.json"
SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) Spec carries Inv 43 ------------------------------------------
spec_low = norm(SPEC_MD.read_text()).lower()

SPEC_REQUIRED = [
    "583",
    "clean-dispatch-leaks.py",
    ".rabbit-scope-active",
    "tdd_last_cycle_impl_commit",
    "before",
    "merge-prs.py",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing Inv 43 phrase(s): {missing!r}")
else:
    ok("spec.md carries the pre-merge leak-cleanup invariant (Inv 43)")

# The critical safety property: never discard unexpected dirt.
if ("never" in spec_low and ("unexpected" in spec_low or "loudly" in spec_low)):
    ok("spec.md states the never-discard-unexpected-dirt safety property")
else:
    fail("spec.md does not state the never-discard-unexpected-dirt property")


# --- (2) Source SKILL.md documents the cleanup step --------------------
if SOURCE_SKILL.is_file():
    skill_low = norm(SOURCE_SKILL.read_text()).lower()
    if "clean-dispatch-leaks.py" in skill_low:
        ok("source SKILL.md documents the pre-merge cleanup step")
    else:
        fail("source SKILL.md does not document clean-dispatch-leaks.py")
else:
    fail(f"source SKILL.md not found at {SOURCE_SKILL}")


# --- (3) Lockstep version across the four versioned artifacts ---------
def frontmatter_version(path):
    text = path.read_text()
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$",
                  text, re.MULTILINE)
    return m.group(1) if m else None


versions = {
    "feature.json": json.loads(FEATURE_JSON.read_text()).get("version"),
    "spec.md": frontmatter_version(SPEC_MD),
    "contract.md": frontmatter_version(CONTRACT_MD),
    "SKILL.md": frontmatter_version(SOURCE_SKILL),
}
if None in versions.values():
    fail(f"could not parse version from all artifacts: {versions!r}")
elif len(set(versions.values())) == 1:
    ok(f"all four versioned artifacts in lockstep at "
       f"{next(iter(versions.values()))} (Inv 15)")
else:
    fail(f"version drift across artifacts: {versions!r}")

sys.exit(FAIL)
