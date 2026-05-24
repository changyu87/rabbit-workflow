#!/usr/bin/env python3
"""Inv 40: manifest declares deployment.

`rabbit-feature.feature.json` declares a `manifest` array of N
publish_skill calls — one per skill in `skills/`. Each entry is
`{"api": "publish_skill", "args": {"source": "skills/<name>/SKILL.md"}}`.
Also asserts `runtime` is a dict and `configuration` is a list (the
two sibling meta-contract arms required by the schema, even when empty).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when publish.json is removed (Plan F) and the
    manifest becomes the sole source of truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"
SKILLS_DIR = FEATURE_DIR / "skills"


def test_manifest_shape() -> None:
    data = json.loads(FEATURE_JSON.read_text())

    assert "manifest" in data, "feature.json missing required top-level 'manifest'"
    assert "runtime" in data, "feature.json missing required top-level 'runtime'"
    assert "configuration" in data, (
        "feature.json missing required top-level 'configuration'"
    )

    manifest = data["manifest"]
    assert isinstance(manifest, list), (
        f"manifest must be list, got {type(manifest).__name__}"
    )
    assert isinstance(data["runtime"], dict), (
        f"runtime must be dict, got {type(data['runtime']).__name__}"
    )
    assert isinstance(data["configuration"], list), (
        f"configuration must be list, got {type(data['configuration']).__name__}"
    )

    skill_dirs = sorted(d.name for d in SKILLS_DIR.iterdir() if d.is_dir())
    assert len(manifest) == len(skill_dirs), (
        f"manifest length {len(manifest)} != number of skill dirs "
        f"{len(skill_dirs)} ({skill_dirs})"
    )

    manifest_sources = set()
    for i, entry in enumerate(manifest):
        assert isinstance(entry, dict), f"manifest[{i}] not a dict"
        assert entry.get("api") == "publish_skill", (
            f"manifest[{i}].api expected 'publish_skill', got {entry.get('api')!r}"
        )
        args = entry.get("args")
        assert isinstance(args, dict), f"manifest[{i}].args must be a dict"
        src = args.get("source")
        assert isinstance(src, str), f"manifest[{i}].args.source must be a string"
        assert src.startswith("skills/") and src.endswith("/SKILL.md"), (
            f"manifest[{i}].args.source must match 'skills/<name>/SKILL.md', "
            f"got {src!r}"
        )
        manifest_sources.add(src)

    expected_sources = {
        f"skills/{name}/SKILL.md" for name in skill_dirs
    }
    assert manifest_sources == expected_sources, (
        f"manifest sources mismatch.\n  got: {sorted(manifest_sources)}\n  "
        f"want: {sorted(expected_sources)}"
    )


if __name__ == "__main__":
    try:
        test_manifest_shape()
        print("PASS test_manifest_shape")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_shape: {e}", file=sys.stderr)
        sys.exit(1)
