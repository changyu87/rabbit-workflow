#!/usr/bin/env python3
"""E2E tests for rabbit-spec SKILL.md process-agnostic invariants (7, 8).

These tests verify that the built SKILL.md at .claude/skills/rabbit-spec/SKILL.md
makes no assumption about a specific caller (e.g., rabbit-feature-touch) being
the primary invocation context, and makes no assumption about a specific
downstream consumer (e.g., the TDD subagent) being a guaranteed next step.

End-to-end scope: the assertions operate on the built/deployed SKILL.md that
real callers would invoke, not just the source under .claude/features/.
"""
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
BUILT_SKILL = os.path.join(REPO_ROOT, ".claude", "skills", "rabbit-spec", "SKILL.md")
SOURCE_SKILL = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-spec", "skills", "rabbit-spec", "SKILL.md"
)


def _read(path):
    with open(path) as f:
        return f.read()


def _split_frontmatter_body(text):
    """Return (frontmatter, body). Assumes YAML frontmatter at start."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    return m.group(1), m.group(2)


def _find_section(body, heading):
    """Return content of a markdown section by heading text (## heading)."""
    pattern = rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else None


def test_built_skill_exists():
    assert os.path.isfile(BUILT_SKILL), f"Built SKILL.md missing at {BUILT_SKILL}"


def test_source_skill_exists():
    assert os.path.isfile(SOURCE_SKILL), f"Source SKILL.md missing at {SOURCE_SKILL}"


def test_built_skill_matches_source():
    """The built copy must mirror the source — drift would let invariants
    pass at the source while the deployed skill violates them."""
    assert _read(BUILT_SKILL) == _read(SOURCE_SKILL), \
        "Built .claude/skills/rabbit-spec/SKILL.md does not match source"


def test_inv7_frontmatter_does_not_name_specific_caller():
    """Invariant 7: description MUST NOT name rabbit-feature-touch as the
    primary/sole trigger."""
    frontmatter, _ = _split_frontmatter_body(_read(BUILT_SKILL))
    desc_match = re.search(r"^description:\s*(.*)$", frontmatter, re.MULTILINE | re.DOTALL)
    assert desc_match, "frontmatter must have a description"
    desc = desc_match.group(1).lower()
    assert "rabbit-feature-touch" not in desc, \
        "description must not name rabbit-feature-touch as a specific trigger"


def test_inv7_body_does_not_name_specific_caller_as_primary():
    """Invariant 7: body MUST NOT identify a specific caller as the primary
    or sole invocation context. The string 'rabbit-feature-touch' must not
    appear in the body at all (the spec lists it only as one example among
    many process-agnostic callers, and the SKILL.md need not enumerate
    callers)."""
    _, body = _split_frontmatter_body(_read(BUILT_SKILL))
    assert "rabbit-feature-touch" not in body.lower(), \
        "body must not mention rabbit-feature-touch as a specific caller"


def test_inv7_body_does_not_name_specific_downstream_consumer():
    """Invariant 7: body MUST NOT reference a specific downstream consumer
    (e.g., 'the TDD subagent reads this file') as a guaranteed next step."""
    _, body = _split_frontmatter_body(_read(BUILT_SKILL))
    lowered = body.lower()
    assert "tdd subagent" not in lowered, \
        "body must not name the TDD subagent as a guaranteed downstream consumer"
    assert "tdd-subagent" not in lowered, \
        "body must not name tdd-subagent as a guaranteed downstream consumer"


def test_inv8_what_you_do_not_do_no_specific_skill_exclusion():
    """Invariant 8: 'What You Do NOT Do' MUST NOT name specific skills to
    avoid invoking. A generic 'do not invoke other skills' rule is OK; a
    process-specific one (e.g., 'do not invoke rabbit-feature-touch') is not."""
    _, body = _split_frontmatter_body(_read(BUILT_SKILL))
    section = _find_section(body, "What You Do NOT Do")
    assert section is not None, "'What You Do NOT Do' section missing"
    lowered = section.lower()
    forbidden_specific_names = [
        "rabbit-feature-touch",
        "rabbit-file",
        "rabbit-project",
        "tdd-subagent",
        "tdd subagent",
    ]
    for name in forbidden_specific_names:
        assert name not in lowered, \
            f"'What You Do NOT Do' must not name a specific skill/process to avoid: found '{name}'"


def test_inv8_what_you_do_not_do_section_present():
    """Sanity check: the 'What You Do NOT Do' section must exist for
    invariant 8 to be meaningful."""
    _, body = _split_frontmatter_body(_read(BUILT_SKILL))
    assert _find_section(body, "What You Do NOT Do") is not None, \
        "SKILL.md must have a 'What You Do NOT Do' section"


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
