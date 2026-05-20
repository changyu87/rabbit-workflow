#!/usr/bin/env python3
"""E2E test: feature.json summary mentions all declared skills.

The two newer skills `rabbit-feature-new` (Inv 33, v1.5.0) and
`rabbit-feature-audit` (Inv 34, v1.6.0) are declared in
`surface.skills` but were initially missing from the human-readable
`summary` field. This test locks the summary against drift.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When the summary field is removed from
feature.json or replaced by a generated view.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FEATURE_JSON = REPO_ROOT / ".claude/features/rabbit-feature/feature.json"

REQUIRED_MENTIONS = ("rabbit-feature-new", "rabbit-feature-audit")


def test_summary_mentions_new_and_audit_skills() -> None:
    manifest = json.loads(FEATURE_JSON.read_text())
    summary = manifest.get("summary", "")
    assert summary, "feature.json must declare a non-empty `summary`"

    missing = [name for name in REQUIRED_MENTIONS if name not in summary]
    assert not missing, (
        "feature.json `summary` must mention these skills declared in "
        f"surface.skills: {missing}. Current summary: {summary!r}"
    )


def main() -> int:
    tests = [test_summary_mentions_new_and_audit_skills]
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
