#!/usr/bin/env python3
"""test-spec-branch-switch-guard-invariant.py — leaked main-HEAD branch-switch
restore (issue #596).

Same root cause as #583 (a subagent's process cwd is sometimes the MAIN/shared
checkout under worktree isolation), but a more severe symptom: a subagent's
`git checkout -B <branch> origin/dev` switches the dispatcher's MAIN HEAD onto a
feature branch, so safety-check Inv 1 ("branch is dev") fails and merge-prs.py
skips the whole batch — with a CLEAN tree (so it is NOT the #583 file-leak path).

The #751 deep slim CONSOLIDATED the branch-switch restore into the same
`clean-dispatch-leaks.py` cleanup invariant as the file-leak class (it is the
SAME script, the SAME Phase-7-first sequencing), so the content is asserted
spec-wide rather than pinned to a specific invariant number.

The restore is INTEGRATION-TARGET-AWARE (Inv 61): the leak is "HEAD is not the
resolved integration target" and the restore checks out that resolved target
(`dev` during the coexistence default, `main` post-cutover), NOT a hardcoded
`dev`. Hardcoding `dev` would wrongly treat the live `main` HEAD as a leak and
switch the dispatcher off `main`.

This e2e regression asserts:

  1. The spec carries the branch-switch-restore text (the leaked
     `git checkout -B`, the HEAD-not-the-resolved-integration-target detection,
     the clean-tree restore to the resolved integration target, the fail-loudly
     refusal on a DIRTY tree or an un-pushed unique commit, and the
     detect/restore-branch-FIRST ordering).
  2. The source SKILL.md documents the branch-restore step.
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


# --- (1) Spec carries the branch-switch-restore content ---------------
spec_low = norm(SPEC_MD.read_text()).lower()

SPEC_REQUIRED = [
    "clean-dispatch-leaks.py",
    "checkout -b",
    "head",
    "integration target",
    "un-pushed",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing branch-switch-restore phrase(s): {missing!r}")
else:
    ok("spec.md carries the leaked-branch-switch restore content")

# Safety property: refuse loudly on dirty/un-pushed, do not discard.
if ("refus" in spec_low or "loudly" in spec_low) and "dirty" in spec_low:
    ok("spec.md states the refuse-loudly-on-dirty/un-pushed safety property")
else:
    fail("spec.md does not state the refuse-on-dirty/un-pushed safety property")

# Ordering: branch restore happens BEFORE the file cleanup.
if "first" in spec_low:
    ok("spec.md states the detect/restore-branch-FIRST ordering")
else:
    fail("spec.md does not state the branch-restore-first ordering")


# --- (2) Source SKILL.md documents the branch-restore step -------------
if SOURCE_SKILL.is_file():
    skill_low = norm(SOURCE_SKILL.read_text()).lower()
    if "head" in skill_low and "integration target" in skill_low:
        ok("source SKILL.md documents the leaked-branch restore step")
    else:
        fail("source SKILL.md does not document the leaked-branch restore step")
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
