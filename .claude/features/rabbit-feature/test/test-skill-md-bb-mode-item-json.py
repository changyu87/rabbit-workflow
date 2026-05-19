#!/usr/bin/env python3
"""E2E test for rabbit-feature Inv 12.

Asserts `rabbit-feature-touch` SKILL.md B/B mode reads `item.json`
(never `bug.json`) and uses Python 3 (not `jq`) for `related_feature`
extraction.

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


def _extract_step_1(text: str) -> str:
    m = re.search(
        r"^###\s+Step\s+1\s+[-—][^\n]*$(.*?)(?=^###\s|^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "SKILL.md is missing a '### Step 1 — ...' section"
    return m.group(1)


def test_bb_mode_uses_item_json_not_bug_json() -> None:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    body = _extract_step_1(SKILL_MD.read_text())
    assert "item.json" in body, (
        "Step 1 B/B mode must reference 'item.json' (unified storage)"
    )
    # Allow the word "bug" in prose (e.g., "bug or backlog") but the legacy
    # path 'bug.json' must NOT appear.
    assert "bug.json" not in body, (
        "Step 1 B/B mode must NOT reference legacy 'bug.json' path"
    )


def test_bb_mode_uses_python3_not_jq() -> None:
    body = _extract_step_1(SKILL_MD.read_text())
    # B/B related_feature extraction must use python3, not jq.
    assert "python3" in body, (
        "Step 1 B/B mode must use 'python3' for related_feature extraction"
    )
    # Forbid the canonical jq extraction pattern. A bare 'jq' substring
    # is risky (could appear in unrelated prose), so check for any jq
    # invocation that looks like data extraction.
    assert not re.search(r"\bjq\s+[-'\"\.]", body), (
        "Step 1 B/B mode must NOT use 'jq' for related_feature extraction "
        "(jq is not a declared dependency of this feature)"
    )


def main() -> int:
    tests = [
        test_bb_mode_uses_item_json_not_bug_json,
        test_bb_mode_uses_python3_not_jq,
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
