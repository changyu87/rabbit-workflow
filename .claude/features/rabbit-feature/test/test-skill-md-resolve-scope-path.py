#!/usr/bin/env python3
"""E2E test for BUG-3: rabbit-feature-scope SKILL.md must reference the
absorbed script path (under rabbit-feature/), not the legacy
rabbit-feature-scope/ path.

After absorption, the source-of-truth resolve-scope.py lives at
.claude/features/rabbit-feature/scripts/resolve-scope.py. The SKILL.md
Usage section's shell command must point at that path.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_MD = REPO_ROOT / ".claude/features/rabbit-feature/skills/rabbit-feature-scope/SKILL.md"
DEPLOYED_SKILL_MD = REPO_ROOT / ".claude/skills/rabbit-feature-scope/SKILL.md"

LEGACY_PATH = ".claude/features/rabbit-feature-scope/scripts/resolve-scope.py"
CORRECT_PATH = ".claude/features/rabbit-feature/scripts/resolve-scope.py"


def test_source_skill_md_uses_correct_resolve_scope_path():
    text = SKILL_MD.read_text()
    assert LEGACY_PATH not in text, (
        f"Source SKILL.md still references legacy path {LEGACY_PATH}"
    )
    assert CORRECT_PATH in text, (
        f"Source SKILL.md missing correct path {CORRECT_PATH}"
    )


def test_deployed_skill_md_uses_correct_resolve_scope_path():
    if not DEPLOYED_SKILL_MD.exists():
        return  # build hasn't been run; source-side test still enforces
    text = DEPLOYED_SKILL_MD.read_text()
    assert LEGACY_PATH not in text, (
        f"Deployed SKILL.md still references legacy path {LEGACY_PATH}"
    )
    assert CORRECT_PATH in text, (
        f"Deployed SKILL.md missing correct path {CORRECT_PATH}"
    )


def main():
    failures = []
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
                failures.append(name)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
