#!/usr/bin/env python3
"""E2E test for rabbit-feature Inv 9.

Asserts `rabbit-feature-touch` SKILL.md documents the
`.rabbit-human-approval-bypass` marker check as the first action of
Step 4 (Human Approval), BEFORE any in-conversation wait or
impl-suggestion surfacing. The warning content must name both the
marker path (`.rabbit-human-approval-bypass`) and the revoke command
(`/rabbit-config bypass-human-approval false`).

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

MARKER_PATH = ".rabbit-human-approval-bypass"
REVOKE_CMD = "/rabbit-config bypass-human-approval false"


def _extract_step_4(text: str) -> str:
    """Return the body of the Step 4 section (up to the next ### heading)."""
    m = re.search(
        r"^###\s+Step\s+4\s+[-—]\s+Human Approval\s*$(.*?)(?=^###\s|^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "SKILL.md is missing a '### Step 4 — Human Approval' section"
    return m.group(1)


def test_step_4_first_action_is_bypass_check() -> None:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    body = _extract_step_4(SKILL_MD.read_text())

    # The marker check must appear before any "wait for ... approval"
    # phrasing and before the impl-suggestion surfacing block.
    marker_pos = body.find(MARKER_PATH)
    assert marker_pos != -1, (
        f"Step 4 does not mention the bypass marker path {MARKER_PATH!r}"
    )

    # "FIRST" prominence: the marker check appears before any mention of
    # surfacing impl-suggestion or waiting for approval.
    surface_pos = body.lower().find("impl-suggestion")
    wait_pos = body.lower().find("wait for explicit")
    for label, pos in [("impl-suggestion", surface_pos), ("wait", wait_pos)]:
        if pos != -1:
            assert marker_pos < pos, (
                f"bypass marker check must appear before {label} "
                f"in Step 4 (marker at {marker_pos}, {label} at {pos})"
            )


def test_step_4_names_marker_path_and_revoke_command() -> None:
    body = _extract_step_4(SKILL_MD.read_text())
    assert MARKER_PATH in body, (
        f"Step 4 must name the marker path {MARKER_PATH!r}"
    )
    assert REVOKE_CMD in body, (
        f"Step 4 must name the revoke command {REVOKE_CMD!r}"
    )


def main() -> int:
    tests = [
        test_step_4_first_action_is_bypass_check,
        test_step_4_names_marker_path_and_revoke_command,
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
