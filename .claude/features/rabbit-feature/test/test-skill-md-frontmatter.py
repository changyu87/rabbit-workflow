#!/usr/bin/env python3
"""Inv 37: SKILL.md frontmatter completeness.

Every SKILL.md declared in `feature.json.surface.skills` MUST declare
non-empty `version`, `owner`, and `deprecation_criterion` fields in its
YAML frontmatter.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when spec-rules.md §3 metadata policy changes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"

REQUIRED_FIELDS = ("version", "owner", "deprecation_criterion")


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, "SKILL.md must start with a YAML frontmatter block"
    return m.group(1)


def test_all_skills_have_required_frontmatter() -> None:
    skills = json.loads(FEATURE_JSON.read_text())["surface"]["skills"]
    assert skills, "feature.json must declare at least one skill"

    failures: list[str] = []
    for rel in skills:
        skill_path = FEATURE_DIR / rel
        assert skill_path.exists(), f"missing SKILL.md: {skill_path}"
        fm = _frontmatter(skill_path.read_text())
        for field in REQUIRED_FIELDS:
            pat = rf"^{re.escape(field)}\s*:\s*\S"
            if not re.search(pat, fm, re.MULTILINE):
                failures.append(f"{rel}: missing or empty `{field}:`")
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    try:
        test_all_skills_have_required_frontmatter()
        print("PASS test_all_skills_have_required_frontmatter")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_all_skills_have_required_frontmatter: {e}", file=sys.stderr)
        sys.exit(1)
