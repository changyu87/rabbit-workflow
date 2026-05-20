#!/usr/bin/env python3
"""E2E regression test for RABBIT-FEATURE-BUG-5.

Asserts the Step 4 bypass warning string in `rabbit-feature-touch`
SKILL.md uses the canonical emoji-framed brand prefix `[\U0001f407 rabbit \U0001f407]`
(per spec Inv 8/9 and contract Inv 35/36 brand convention), and does
NOT contain the bare `[rabbit]` form.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When the rabbit brand convention changes
(tied to contract Inv 35/36 lifecycle).
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
DEPLOYED_SKILL_MD = REPO_ROOT / ".claude/skills/rabbit-feature-touch/SKILL.md"

CANONICAL_BRAND = "[\U0001f407 rabbit \U0001f407]"
BARE_BRAND = "[rabbit]"
WARNING_NEEDLE = "Step 4 SKIPPED"


def _extract_warning_line(text: str) -> str:
    """Return the line containing the Step 4 bypass warning string."""
    for line in text.splitlines():
        if WARNING_NEEDLE in line:
            return line
    raise AssertionError(
        f"SKILL.md does not contain a {WARNING_NEEDLE!r} warning line"
    )


def _check_brand_in_warning(skill_md_path: Path, label: str) -> None:
    assert skill_md_path.exists(), f"missing SKILL.md: {skill_md_path}"
    text = skill_md_path.read_text(encoding="utf-8")
    warning_line = _extract_warning_line(text)
    assert CANONICAL_BRAND in warning_line, (
        f"[{label}] Step 4 bypass warning must contain canonical brand "
        f"{CANONICAL_BRAND!r}; got line: {warning_line!r}"
    )
    assert BARE_BRAND not in warning_line, (
        f"[{label}] Step 4 bypass warning must NOT contain bare brand "
        f"{BARE_BRAND!r}; got line: {warning_line!r}"
    )


def test_source_skill_md_uses_canonical_brand() -> None:
    _check_brand_in_warning(SKILL_MD, "source")


def test_deployed_skill_md_uses_canonical_brand() -> None:
    _check_brand_in_warning(DEPLOYED_SKILL_MD, "deployed")


def main() -> int:
    tests = [
        test_source_skill_md_uses_canonical_brand,
        test_deployed_skill_md_uses_canonical_brand,
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
