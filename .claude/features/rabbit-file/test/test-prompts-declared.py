#!/usr/bin/env python3
"""CONTRACT-BACKLOG-1 Phase C: feature.json declares the prompts contract.

`rabbit-file.feature.json` MUST declare a `prompts` array with EXACTLY one
entry describing the rabbit-file skill prompt assembly:

  {"id": "rabbit-file",
   "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["args"]}

The skill files bugs and edits item.json — code-authoring — so it needs
philosophy + coding-rules (not spec-rules; rabbit-file does not author
specs). The matching template at
`.claude/features/contract/templates/prompts/rabbit-file.txt` supplies the
body via `slots: ["args"]`.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when prompt-contract assembly is native to Claude Code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"

EXPECTED_ENTRY = {
    "id": "rabbit-file",
    "kind": "skill",
    "inject": [
        ".claude/features/policy/philosophy.md",
        ".claude/features/policy/coding-rules.md",
    ],
    "slots": ["args"],
}


def test_prompts_declared() -> None:
    data = json.loads(FEATURE_JSON.read_text())

    assert "prompts" in data, "feature.json missing required top-level 'prompts'"
    prompts = data["prompts"]
    assert isinstance(prompts, list), (
        f"prompts must be list, got {type(prompts).__name__}"
    )
    assert len(prompts) == 1, (
        f"prompts must have exactly 1 entry per spec, got {len(prompts)}"
    )

    entry = prompts[0]
    assert isinstance(entry, dict), (
        f"prompts[0] not a dict, got {type(entry).__name__}"
    )
    assert entry.get("id") == EXPECTED_ENTRY["id"], (
        f"prompts[0].id expected {EXPECTED_ENTRY['id']!r}, got {entry.get('id')!r}"
    )
    assert entry.get("kind") == EXPECTED_ENTRY["kind"], (
        f"prompts[0].kind expected {EXPECTED_ENTRY['kind']!r}, got {entry.get('kind')!r}"
    )
    assert entry.get("inject") == EXPECTED_ENTRY["inject"], (
        f"prompts[0].inject expected {EXPECTED_ENTRY['inject']!r}, got {entry.get('inject')!r}"
    )
    assert entry.get("slots") == EXPECTED_ENTRY["slots"], (
        f"prompts[0].slots expected {EXPECTED_ENTRY['slots']!r}, got {entry.get('slots')!r}"
    )


if __name__ == "__main__":
    try:
        test_prompts_declared()
        print("PASS test_prompts_declared")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_prompts_declared: {e}", file=sys.stderr)
        sys.exit(1)
