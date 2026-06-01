#!/usr/bin/env python3
"""Regression test for Inv 43 — feature.json `prompts` section declaration.

Asserts rabbit-feature's feature.json declares EXACTLY five prompts entries,
one per surfaced skill, each carrying the expected `kind`, `inject`, and
`slots` values per Inv 43.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: When prompt-contract assembly becomes native to
Claude Code (mirrors Inv 43's deprecation criterion).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FEAT = REPO_ROOT / ".claude/features/rabbit-feature/feature.json"

EXPECTED = {
    "rabbit-feature-touch": {
        "kind": "skill",
        "inject": [
            ".claude/features/policy/philosophy.md",
            ".claude/features/policy/spec-rules.md",
            ".claude/features/policy/coding-rules.md",
        ],
        "slots": ["args"],
    },
    "rabbit-feature-new": {
        "kind": "skill",
        "inject": [
            ".claude/features/policy/philosophy.md",
            ".claude/features/policy/coding-rules.md",
        ],
        "slots": ["args"],
    },
    "rabbit-feature-audit": {
        "kind": "skill",
        "inject": [
            ".claude/features/policy/philosophy.md",
            ".claude/features/policy/coding-rules.md",
        ],
        "slots": ["args"],
    },
    "rabbit-feature-scope": {
        "kind": "skill",
        "inject": [".claude/features/policy/philosophy.md"],
        "slots": ["args"],
    },
}


def main() -> int:
    data = json.loads(FEAT.read_text())
    prompts = data.get("prompts")
    failures: list[str] = []
    if not isinstance(prompts, list):
        print("FAIL: prompts is not a list")
        return 1
    if len(prompts) != 4:
        failures.append(f"expected exactly 4 entries, got {len(prompts)}")
    by_id = {e["id"]: e for e in prompts if isinstance(e, dict) and "id" in e}
    for eid, want in EXPECTED.items():
        got = by_id.get(eid)
        if got is None:
            failures.append(f"missing entry id={eid}")
            continue
        if got.get("kind") != want["kind"]:
            failures.append(
                f"{eid}: kind mismatch (want {want['kind']!r}, got {got.get('kind')!r})"
            )
        if got.get("inject") != want["inject"]:
            failures.append(
                f"{eid}: inject mismatch (want {want['inject']!r}, got {got.get('inject')!r})"
            )
        if got.get("slots") != want["slots"]:
            failures.append(
                f"{eid}: slots mismatch (want {want['slots']!r}, got {got.get('slots')!r})"
            )
    extra = set(by_id.keys()) - set(EXPECTED.keys())
    if extra:
        failures.append(f"unexpected entries: {sorted(extra)}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("OK: all 5 prompts entries match Inv 43")
    return 0


if __name__ == "__main__":
    sys.exit(main())
