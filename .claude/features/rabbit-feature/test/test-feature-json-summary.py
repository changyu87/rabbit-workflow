#!/usr/bin/env python3
"""Inv 38: feature.json summary mentions every declared skill.

`feature.json.summary` MUST mention by name every skill declared in
`feature.json.surface.skills`.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the summary field is removed from feature.json
or replaced by a generated view.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FEATURE_JSON = Path(__file__).resolve().parents[1] / "feature.json"


def _skill_name(rel_path: str) -> str:
    # "skills/rabbit-feature-touch/SKILL.md" -> "rabbit-feature-touch"
    return rel_path.split("/")[1]


def test_summary_mentions_every_skill() -> None:
    data = json.loads(FEATURE_JSON.read_text())
    summary = data.get("summary", "")
    assert summary, "feature.json must declare a non-empty `summary`"
    skills = data["surface"]["skills"]
    missing = [_skill_name(s) for s in skills if _skill_name(s) not in summary]
    assert not missing, (
        f"feature.json `summary` must mention every skill in surface.skills; "
        f"missing: {missing}; summary: {summary!r}"
    )


if __name__ == "__main__":
    try:
        test_summary_mentions_every_skill()
        print("PASS test_summary_mentions_every_skill")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_summary_mentions_every_skill: {e}", file=sys.stderr)
        sys.exit(1)
