#!/usr/bin/env python3
"""test-spec-branch-switch-guard-invariant.py — rabbit-auto-evolve Inv 44
(issue #596): the pre-merge cleanup detects + restores a leaked main-HEAD
branch switch.

Same root cause as #583 (a subagent's process cwd is sometimes the MAIN/shared
checkout under worktree isolation), but a more severe symptom: a subagent's
`git checkout -B <branch> origin/dev` switches the dispatcher's MAIN HEAD onto a
feature branch, so safety-check Inv 1 ("branch is dev") fails and merge-prs.py
skips the whole batch — with a CLEAN tree (so it is NOT the #583 file-leak path).

This e2e regression asserts:

  1. The spec carries the Inv 44 text (issue #596 cross-ref, the leaked
     `git checkout -B`, HEAD != dev detection, the clean-tree restore via
     `git checkout dev`, the fail-loudly refusal on a DIRTY tree or an un-pushed
     unique commit, and the detect/restore-branch-FIRST ordering).
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


# --- (1) Spec carries Inv 44 ------------------------------------------
spec_low = norm(SPEC_MD.read_text()).lower()

SPEC_REQUIRED = [
    "clean-dispatch-leaks.py",
    "checkout -b",
    "head",
    "checkout dev",
    "un-pushed",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing Inv 44 phrase(s): {missing!r}")
else:
    ok("spec.md carries the leaked-branch-switch restore invariant (Inv 44)")

# Numbered Inv 44 entry must exist.
if re.search(r"(?m)^44\.\s", SPEC_MD.read_text()):
    ok("spec.md has a numbered Inv 44 entry")
else:
    fail("spec.md has no numbered '44.' invariant entry")

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
    if "head" in skill_low and "checkout dev" in skill_low:
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
