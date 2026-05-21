#!/usr/bin/env python3
"""E2E test: rabbit-feature-touch SKILL.md invokes rabbit-feature-spec.

Locks the positive Step-3 invocation: SKILL.md MUST invoke
`Skill("rabbit-feature-spec", ...)` for spec authoring.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_MD = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"
)


def test_skill_md_exists() -> None:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"


def test_invokes_rabbit_feature_spec() -> None:
    body = SKILL_MD.read_text()
    # The renamed skill invocation must appear.
    assert 'Skill("rabbit-feature-spec"' in body, (
        'SKILL.md must invoke Skill("rabbit-feature-spec", ...) '
        "for Step 3 spec authoring"
    )


def main() -> int:
    tests = [
        test_skill_md_exists,
        test_invokes_rabbit_feature_spec,
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
