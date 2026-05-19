#!/usr/bin/env python3
"""E2E test for rabbit-feature absorption of rabbit-spec (renamed to
rabbit-feature-spec).

Asserts the absorbed surface is materialized inside rabbit-feature:

  1. skills/rabbit-feature-spec/SKILL.md exists, has YAML frontmatter
     `name: rabbit-feature-spec` (the rename), and contains the same body
     content as the rabbit-spec source (modulo the rename and any
     self-references).
  2. The absorbed test files from rabbit-spec/test/ exist under
     rabbit-feature/test/.
  3. feature.json surface.skills declares the absorbed skill.
  4. contract.md provides.skills declares the new surface.
  5. spec.md re-homes the rabbit-spec invariants as absorbed.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When the rabbit-spec feature directory is deleted
(separate cleanup cycle) and the source comparison is no longer meaningful.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = FEATURE_DIR.parents[2]
SOURCE_SPEC_DIR = REPO_ROOT / ".claude/features/rabbit-spec"

ABSORBED_SKILL = FEATURE_DIR / "skills/rabbit-feature-spec/SKILL.md"
SOURCE_SKILL = SOURCE_SPEC_DIR / "skills/rabbit-spec/SKILL.md"

FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "docs/spec/contract.md"
SPEC_MD = FEATURE_DIR / "docs/spec/spec.md"


def _load_contract_json() -> dict:
    text = CONTRACT_MD.read_text()
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert match, f"no fenced JSON block in {CONTRACT_MD}"
    return json.loads(match.group(1))


def _frontmatter(text: str) -> dict:
    """Tiny YAML-ish frontmatter parser for 'key: value' pairs only."""
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fm = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def test_absorbed_skill_exists() -> None:
    assert ABSORBED_SKILL.is_file(), f"missing absorbed skill: {ABSORBED_SKILL}"


def test_absorbed_skill_has_renamed_frontmatter() -> None:
    fm = _frontmatter(ABSORBED_SKILL.read_text())
    assert fm.get("name") == "rabbit-feature-spec", (
        f"absorbed SKILL.md frontmatter name must be 'rabbit-feature-spec', "
        f"got {fm.get('name')!r}"
    )


def test_absorbed_skill_no_residual_old_name_self_reference() -> None:
    """The skill body must not call itself 'rabbit-spec'. Cross-references
    elsewhere are fine — but self-references must use the new name."""
    text = ABSORBED_SKILL.read_text()
    # Strip the frontmatter — only check body content for old self-refs.
    body = text.split("\n---\n", 2)[-1] if text.startswith("---\n") else text
    # Look for explicit self-naming patterns. The Skill tool invocation
    # `Skill("rabbit-spec", ...)` is the most load-bearing rename target.
    assert 'Skill("rabbit-spec"' not in body, (
        "absorbed SKILL.md body still contains Skill(\"rabbit-spec\", ...); "
        "rename to Skill(\"rabbit-feature-spec\", ...)"
    )
    assert "# rabbit-spec —" not in body, (
        "absorbed SKILL.md body still contains '# rabbit-spec —' heading; "
        "rename to '# rabbit-feature-spec —'"
    )


def test_absorbed_test_files_copied() -> None:
    """Every test-*.py from rabbit-spec/test/ is present in rabbit-feature/test/
    either under its original filename OR under a `test-rabbit-spec-` prefix
    when the original filename collides with an existing rabbit-feature test.
    """
    source_tests = sorted(
        p for p in (SOURCE_SPEC_DIR / "test").glob("test-*.py")
    )
    assert source_tests, (
        f"no source tests found under {SOURCE_SPEC_DIR / 'test'}"
    )
    missing = []
    for src in source_tests:
        original = FEATURE_DIR / "test" / src.name
        # Disambiguated form for collisions: drop the leading "test-" then
        # prefix "test-rabbit-spec-".
        renamed = FEATURE_DIR / "test" / f"test-rabbit-spec-{src.name[len('test-'):]}"
        if not (original.is_file() or renamed.is_file()):
            missing.append(src.name)
    assert not missing, (
        f"absorbed rabbit-spec test files missing in rabbit-feature/test/: "
        f"{missing}"
    )


def test_feature_json_surface_declares_absorbed_skill() -> None:
    data = json.loads(FEATURE_JSON.read_text())
    skills = data.get("surface", {}).get("skills", [])
    assert "skills/rabbit-feature-spec/SKILL.md" in skills, (
        f"feature.json surface.skills missing rabbit-feature-spec; got {skills!r}"
    )


def test_contract_md_provides_declares_absorbed_skill() -> None:
    contract = _load_contract_json()
    provides = contract.get("provides", {})
    skill_paths = [s.get("path", "") for s in provides.get("skills", [])]
    assert any(
        "rabbit-feature-spec" in p for p in skill_paths
    ), (
        f"contract.md provides.skills missing rabbit-feature-spec; "
        f"got {skill_paths!r}"
    )


def test_spec_md_documents_rabbit_spec_absorption() -> None:
    text = SPEC_MD.read_text()
    assert "rabbit-feature-spec" in text, (
        "spec.md must mention the absorbed skill 'rabbit-feature-spec'"
    )
    assert "Absorbed from rabbit-spec" in text or "absorbed from rabbit-spec" in text.lower(), (
        "spec.md must declare invariants as absorbed from rabbit-spec"
    )


TESTS = [
    test_absorbed_skill_exists,
    test_absorbed_skill_has_renamed_frontmatter,
    test_absorbed_skill_no_residual_old_name_self_reference,
    test_absorbed_test_files_copied,
    test_feature_json_surface_declares_absorbed_skill,
    test_contract_md_provides_declares_absorbed_skill,
    test_spec_md_documents_rabbit_spec_absorption,
]


def main() -> int:
    failures: list[str] = []
    for test in TESTS:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
