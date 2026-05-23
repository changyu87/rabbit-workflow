#!/usr/bin/env python3
"""Inv 1: build source for rabbit-feature-touch SKILL.md.

The deployed `.claude/skills/rabbit-feature-touch/SKILL.md` is sourced from
`.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`. The
per-feature `publish.json` declares a `targets` entry named
`skills/rabbit-feature-touch/SKILL.md` whose `source` field matches that
path exactly (feature-relative).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when publish.json is superseded by the meta-contract
manifest mechanism (Plan F).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
PUBLISH = FEATURE_DIR / "publish.json"
ENTRY_NAME = "skills/rabbit-feature-touch/SKILL.md"
EXPECTED_SOURCE = "skills/rabbit-feature-touch/SKILL.md"


def test_publish_json_declares_touch_skill_target() -> None:
    assert PUBLISH.is_file(), f"missing publish manifest: {PUBLISH}"
    data = json.loads(PUBLISH.read_text())
    targets = data.get("targets", [])
    matches = [t for t in targets if t.get("name") == ENTRY_NAME]
    assert len(matches) == 1, (
        f"expected exactly one publish.json target named {ENTRY_NAME!r}; got {len(matches)}"
    )
    src = matches[0].get("source")
    assert src == EXPECTED_SOURCE, (
        f"publish.json target {ENTRY_NAME!r} has source={src!r}; expected {EXPECTED_SOURCE!r}"
    )


if __name__ == "__main__":
    try:
        test_publish_json_declares_touch_skill_target()
        print("PASS test_publish_json_declares_touch_skill_target")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_publish_json_declares_touch_skill_target: {e}", file=sys.stderr)
        sys.exit(1)
