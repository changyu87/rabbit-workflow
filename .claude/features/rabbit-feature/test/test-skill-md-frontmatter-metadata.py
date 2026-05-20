#!/usr/bin/env python3
"""E2E test: every SKILL.md under rabbit-feature declares full metadata.

Per spec-rules.md §3 (Lifecycle and Ownership), every skill SKILL.md
MUST declare `version`, `owner`, and `deprecation_criterion` in its
YAML frontmatter. An artifact missing any of these in its declared
location is unowned and must be promoted to compliance.

This test covers all SKILL.md files declared in feature.json.surface.skills
and asserts each contains the three required frontmatter fields.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When the spec-rules metadata policy is replaced
or removed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FEATURE_DIR = REPO_ROOT / ".claude/features/rabbit-feature"
FEATURE_JSON = FEATURE_DIR / "feature.json"

REQUIRED_FIELDS = ("version", "owner", "deprecation_criterion")


def _frontmatter(text: str) -> str:
    """Return the YAML frontmatter block (between the first two `---`)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, "SKILL.md must start with a YAML frontmatter block"
    return m.group(1)


def test_all_skills_have_required_frontmatter() -> None:
    manifest = json.loads(FEATURE_JSON.read_text())
    skills = manifest.get("surface", {}).get("skills", [])
    assert skills, "feature.json must declare at least one skill"

    failures: list[str] = []
    for rel in skills:
        skill_path = FEATURE_DIR / rel
        assert skill_path.exists(), f"missing SKILL.md: {skill_path}"
        fm = _frontmatter(skill_path.read_text())
        for field in REQUIRED_FIELDS:
            # Match the key at line-start followed by `:` and a non-empty value.
            pat = rf"^{re.escape(field)}\s*:\s*\S"
            if not re.search(pat, fm, re.MULTILINE):
                failures.append(f"{rel}: missing or empty `{field}:` in frontmatter")
    assert not failures, "\n".join(failures)


def main() -> int:
    tests = [test_all_skills_have_required_frontmatter]
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
