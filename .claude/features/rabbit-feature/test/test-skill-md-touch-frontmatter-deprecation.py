#!/usr/bin/env python3
"""E2E test: rabbit-feature-touch SKILL.md frontmatter is current.

The `deprecation_criterion` MUST NOT reference deleted infrastructure
(specifically `dispatch-feature-edit.py`, removed in BUG-94). An
artifact whose deprecation criterion cites a non-existent successor
is unowned (spec-rules §3) — the criterion can never trigger.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively
handled by the rabbit CLI or by Claude Code's native workflow
mechanism.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_MD = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"
)


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, "SKILL.md must start with a YAML frontmatter block"
    return m.group(1)


def test_deprecation_criterion_no_stale_ref() -> None:
    fm = _frontmatter(SKILL_MD.read_text())
    m = re.search(
        r"^deprecation_criterion\s*:\s*(.+)$", fm, re.MULTILINE
    )
    assert m, "frontmatter must declare `deprecation_criterion:`"
    value = m.group(1).strip()
    assert "dispatch-feature-edit" not in value, (
        "deprecation_criterion must not reference the deleted "
        "dispatch-feature-edit.py (removed in BUG-94); cite a live "
        "successor instead. Current value: " + value
    )


def main() -> int:
    tests = [test_deprecation_criterion_no_stale_ref]
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
