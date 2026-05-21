#!/usr/bin/env python3
"""E2E test locking the rabbit-feature/publish.json source for rabbit-feature-touch.

Parses `.claude/features/rabbit-feature/publish.json`, locates the entry
named `skills/rabbit-feature-touch/SKILL.md`, and asserts its `source` field
equals `skills/rabbit-feature-touch/SKILL.md` (relative to the feature dir).

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
RABBIT_FEATURE_DIR = REPO_ROOT / ".claude/features/rabbit-feature"
PUBLISH = RABBIT_FEATURE_DIR / "publish.json"
ENTRY_NAME = "skills/rabbit-feature-touch/SKILL.md"
EXPECTED_SOURCE = "skills/rabbit-feature-touch/SKILL.md"


def test_build_source_points_to_rabbit_feature() -> None:
    assert PUBLISH.exists(), f"missing publish manifest: {PUBLISH}"
    data = json.loads(PUBLISH.read_text())
    targets = data.get("targets", [])
    matches = [t for t in targets if t.get("name") == ENTRY_NAME]
    assert len(matches) == 1, (
        f"expected exactly one publish.json entry named {ENTRY_NAME!r}, "
        f"got {len(matches)}"
    )
    entry = matches[0]
    actual_source = entry.get("source")
    assert actual_source == EXPECTED_SOURCE, (
        f"publish.json entry {ENTRY_NAME!r} has source={actual_source!r}, "
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
