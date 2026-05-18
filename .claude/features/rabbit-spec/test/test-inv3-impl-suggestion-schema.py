#!/usr/bin/env python3
"""E2E test for rabbit-spec Invariant 3 (impl-suggestion schema conformance).

Invariant 3 requires that rabbit-spec writes
`.rabbit/impl-suggestion-<feature>.json` conforming to schema_version 1.0.0 on
every invocation. This test asserts the deployed (built) SKILL.md body
documents every required field of the impl-suggestion schema, so any
implementer following the skill produces a conforming file.

End-to-end scope: the test operates on the built/deployed SKILL.md that real
callers invoke, not just the source under .claude/features/.
"""
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
BUILT_SKILL = os.path.join(REPO_ROOT, ".claude", "skills", "rabbit-spec", "SKILL.md")
SOURCE_SKILL = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-spec", "skills", "rabbit-spec", "SKILL.md"
)

REQUIRED_FIELDS = [
    "schema_version",
    "feature",
    "generated_at",
    "request_summary",
    "spec_changes",
    "implementation_approach",
    "affected_files",
    "key_invariants",
]


def _read(path):
    with open(path) as f:
        return f.read()


def _split_frontmatter_body(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    return m.group(1), m.group(2)


def test_built_skill_exists():
    assert os.path.isfile(BUILT_SKILL), f"Built SKILL.md missing at {BUILT_SKILL}"


def test_body_documents_all_required_schema_fields():
    """Inv 3: SKILL.md body MUST document every required impl-suggestion
    schema field, so implementers produce a conforming file."""
    _, body = _split_frontmatter_body(_read(BUILT_SKILL))
    for field in REQUIRED_FIELDS:
        # Field must appear as a JSON key in the body (e.g., "schema_version":).
        pattern = rf'"{re.escape(field)}"\s*:'
        assert re.search(pattern, body), \
            f"SKILL.md body must document required schema field '{field}'"


def test_body_documents_schema_version_value():
    """The documented schema_version value must be 1.0.0 (matches spec)."""
    _, body = _split_frontmatter_body(_read(BUILT_SKILL))
    assert re.search(r'"schema_version"\s*:\s*"1\.0\.0"', body), \
        "SKILL.md must document schema_version 1.0.0"


def test_body_references_impl_suggestion_output_path():
    """The skill must instruct writing to .rabbit/impl-suggestion-<...>.json."""
    _, body = _split_frontmatter_body(_read(BUILT_SKILL))
    assert ".rabbit/impl-suggestion-" in body, \
        "SKILL.md must reference the .rabbit/impl-suggestion-<feature>.json output path"


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
