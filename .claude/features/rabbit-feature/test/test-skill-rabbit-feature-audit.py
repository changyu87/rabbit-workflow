#!/usr/bin/env python3
"""E2E test for rabbit-feature BACKLOG-3 (Inv 34).

Asserts the `rabbit-feature-audit` skill is present and conforms to spec:
- SKILL.md exists at skills/rabbit-feature-audit/SKILL.md
- frontmatter declares name=rabbit-feature-audit with required metadata
  (description, version, owner, deprecation_criterion)
- body documents the protocol: 'all' and '<feature-name>' args, uses
  contract.lib.checks.validate_feature, produces per-feature pass/fail
- feature.json surface.skills includes the new skill
- contract.md provides.skills includes the new skill directory

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FEATURE_DIR = REPO_ROOT / ".claude/features/rabbit-feature"
SKILL_MD = FEATURE_DIR / "skills/rabbit-feature-audit/SKILL.md"
FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "docs/spec/contract.md"


def _frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, "SKILL.md is missing YAML frontmatter"
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def test_skill_md_exists() -> None:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"


def test_frontmatter_required_fields() -> None:
    fm = _frontmatter(SKILL_MD.read_text())
    assert fm.get("name") == "rabbit-feature-audit", (
        f"frontmatter name must be 'rabbit-feature-audit', got {fm.get('name')!r}"
    )
    for key in ("description", "version", "owner", "deprecation_criterion"):
        assert fm.get(key), f"frontmatter missing required field: {key}"


def test_body_documents_protocol() -> None:
    text = SKILL_MD.read_text()
    # Args modes
    assert "all" in text, "SKILL.md body must document the 'all' args mode"
    assert "<feature-name>" in text or "feature-name" in text, (
        "SKILL.md body must document the single '<feature-name>' args mode"
    )
    # Backing library
    assert "validate_feature" in text, (
        "SKILL.md body must reference contract.lib.checks.validate_feature"
    )
    # Output shape
    assert "pass" in text.lower() and "fail" in text.lower(), (
        "SKILL.md body must describe per-feature pass/fail output"
    )


def test_feature_json_surface_lists_skill() -> None:
    data = json.loads(FEATURE_JSON.read_text())
    skills = data.get("surface", {}).get("skills", [])
    assert "skills/rabbit-feature-audit/SKILL.md" in skills, (
        "feature.json surface.skills must list skills/rabbit-feature-audit/SKILL.md; "
        f"got {skills}"
    )


def test_contract_md_provides_skill() -> None:
    text = CONTRACT_MD.read_text()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert m, "contract.md missing JSON block"
    data = json.loads(m.group(1))
    skill_paths = [s.get("path", "") for s in data.get("provides", {}).get("skills", [])]
    expected = ".claude/features/rabbit-feature/skills/rabbit-feature-audit/"
    assert expected in skill_paths, (
        f"contract.md provides.skills must include {expected}; got {skill_paths}"
    )


def main() -> int:
    tests = [
        test_skill_md_exists,
        test_frontmatter_required_fields,
        test_body_documents_protocol,
        test_feature_json_surface_lists_skill,
        test_contract_md_provides_skill,
    ]
    failures: list[str] = []
    for test in tests:
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
