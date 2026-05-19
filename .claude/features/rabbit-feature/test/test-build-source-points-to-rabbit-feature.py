#!/usr/bin/env python3
"""E2E test locking the build-contract.json source for rabbit-feature-touch.

Parses `.claude/features/contract/build-contract.json`, locates the entry
named `skills/rabbit-feature-touch/SKILL.md`, and asserts its `source` field
equals `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`.

If anything re-points the build to a different source (e.g., back to the
tdd-subagent source, or to a typo'd path), this test fails and forces
rabbit-feature into red state (spec Inv 4).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BUILD_CONTRACT = REPO_ROOT / ".claude/features/contract/build-contract.json"
ENTRY_NAME = "skills/rabbit-feature-touch/SKILL.md"
EXPECTED_SOURCE = ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"


def test_build_source_points_to_rabbit_feature() -> None:
    assert BUILD_CONTRACT.exists(), f"missing build contract: {BUILD_CONTRACT}"
    data = json.loads(BUILD_CONTRACT.read_text())
    targets = data.get("targets", [])
    matches = [t for t in targets if t.get("name") == ENTRY_NAME]
    assert len(matches) == 1, (
        f"expected exactly one build-contract entry named {ENTRY_NAME!r}, "
        f"got {len(matches)}"
    )
    entry = matches[0]
    actual_source = entry.get("source")
    assert actual_source == EXPECTED_SOURCE, (
        f"build-contract entry {ENTRY_NAME!r} has source={actual_source!r}, "
        f"expected {EXPECTED_SOURCE!r}"
    )


def main() -> int:
    tests = [test_build_source_points_to_rabbit_feature]
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
