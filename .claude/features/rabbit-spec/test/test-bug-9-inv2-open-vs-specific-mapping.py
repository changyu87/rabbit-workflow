#!/usr/bin/env python3
"""E2E test for rabbit-spec Invariant 2 (open-vs-specific judgment mapping).

Invariant 2 requires rabbit-spec to judge whether a request is open-ended or
specific BEFORE deciding which superpowers to invoke:
  - open     -> brainstorming + writing-plans
  - specific -> writing-plans only

This test parses the deployed (built) SKILL.md and asserts both mappings
appear in the judgment / superpower-invocation section, so any implementer
following SKILL.md picks the right superpowers.

Closes RABBIT-SPEC-BACKLOG-9 test gap (b).
"""
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
BUILT_SKILL = os.path.join(REPO_ROOT, ".claude", "skills", "rabbit-spec", "SKILL.md")


def _read(path):
    with open(path) as f:
        return f.read()


def _section(text, heading_pattern):
    """Return content of a markdown ## section whose heading matches the
    given regex (no anchors)."""
    m = re.search(
        rf"^##\s+{heading_pattern}\s*\n(.*?)(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else None


def test_built_skill_exists():
    assert os.path.isfile(BUILT_SKILL), f"Built SKILL.md missing at {BUILT_SKILL}"


def test_open_ended_maps_to_brainstorming_then_writing_plans():
    """Inv 2: open-ended branch MUST invoke brainstorming AND writing-plans."""
    text = _read(BUILT_SKILL)
    section = _section(text, r"Step\s+3.*Invoke\s+Superpowers")
    assert section is not None, \
        "SKILL.md must have a 'Step 3 — Invoke Superpowers' section"
    # Find the open-ended sub-block: bounded between an "open" header and
    # the next bold sub-header (e.g., "If specific:") or end of section.
    m = re.search(
        r"\*\*If\s+open-ended:\*\*(.*?)(?:\*\*If\s+specific:\*\*|\Z)",
        section, re.DOTALL | re.IGNORECASE,
    )
    assert m is not None, \
        "Step 3 must have an '**If open-ended:**' sub-block"
    open_block = m.group(1).lower()
    assert "brainstorming" in open_block, \
        "open-ended branch must reference superpowers:brainstorming"
    assert "writing-plans" in open_block or "writing_plans" in open_block, \
        "open-ended branch must reference superpowers:writing-plans"


def test_specific_maps_to_writing_plans_only():
    """Inv 2: specific branch MUST invoke writing-plans only (no
    brainstorming)."""
    text = _read(BUILT_SKILL)
    section = _section(text, r"Step\s+3.*Invoke\s+Superpowers")
    assert section is not None
    m = re.search(
        r"\*\*If\s+specific:\*\*(.*?)(?=^##\s|\Z)",
        section, re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )
    assert m is not None, \
        "Step 3 must have an '**If specific:**' sub-block"
    specific_block = m.group(1).lower()
    assert "writing-plans" in specific_block or "writing_plans" in specific_block, \
        "specific branch must reference superpowers:writing-plans"
    # Must NOT call brainstorming inside the specific branch.
    # (We check the literal superpower invocation, not the word
    # "brainstorming" appearing in commentary like "No brainstorming needed".)
    assert "superpowers:brainstorming" not in specific_block, \
        "specific branch must NOT invoke superpowers:brainstorming"


def test_judgment_step_precedes_invocation_step():
    """Inv 2: judgment (Step 2) MUST come before superpower invocation
    (Step 3) — the skill judges first, then invokes."""
    text = _read(BUILT_SKILL)
    m2 = re.search(r"^##\s+Step\s+2.*Judge\s+Request\s+Type", text, re.MULTILINE)
    m3 = re.search(r"^##\s+Step\s+3.*Invoke\s+Superpowers", text, re.MULTILINE)
    assert m2 is not None, "SKILL.md must have a 'Step 2 — Judge Request Type' heading"
    assert m3 is not None, "SKILL.md must have a 'Step 3 — Invoke Superpowers' heading"
    assert m2.start() < m3.start(), \
        "Judgment step must precede superpower invocation step"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
