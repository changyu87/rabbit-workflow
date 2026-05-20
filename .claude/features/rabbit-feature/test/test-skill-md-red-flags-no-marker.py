#!/usr/bin/env python3
"""E2E test for rabbit-feature Inv 11.

Asserts `rabbit-feature-touch` SKILL.md Red Flags section includes the
rule: main session MUST NOT create `.rabbit-scope-active` (global) or
`.rabbit-scope-active-<feature>` (per-feature) scope markers at the
repo root.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
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


def _extract_red_flags(text: str) -> str:
    m = re.search(
        r"^##\s+Red Flags[^\n]*$(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "SKILL.md is missing a '## Red Flags' section"
    return m.group(1)


def test_red_flags_prohibit_main_session_scope_marker_creation() -> None:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    body = _extract_red_flags(SKILL_MD.read_text())
    lower = body.lower()
    assert ".rabbit-scope-active" in body, (
        "Red Flags must reference '.rabbit-scope-active' marker name"
    )
    assert ".rabbit-scope-active-" in body, (
        "Red Flags must reference '.rabbit-scope-active-<feature>' "
        "per-feature marker pattern"
    )
    assert "main session" in lower, (
        "Red Flags must mention 'main session' marker-creation prohibition"
    )


def main() -> int:
    tests = [test_red_flags_prohibit_main_session_scope_marker_creation]
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
