#!/usr/bin/env python3
"""tdd-state-machine: manifest declares deployment.

`tdd-state-machine.feature.json` declares meta-contract sections:
  - `manifest`: list of length 1 with the single publish_file entry
    `{"api": "publish_file", "args": {"source": "scripts/tdd-step.py",
    "dest": ".claude/agents/tdd-subagent/scripts/tdd-step.py"}}`.
  - `runtime`: `{}` (no event hook handlers; consistent with surface.hooks=[]).
  - `configuration`: `[]` (no configurable toggles).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature lifecycle management is natively
    handled by Claude Code's workflow mechanism.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"

EXPECTED_SOURCE = "scripts/tdd-step.py"
EXPECTED_DEST = ".claude/agents/tdd-subagent/scripts/tdd-step.py"


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

    assert data["runtime"] == {}, (
        f"runtime must be empty dict per spec, got {data['runtime']!r}"
    )
    assert data["configuration"] == [], (
        f"configuration must be empty list per spec, got {data['configuration']!r}"
    )

    assert len(manifest) == 1, (
        f"manifest must have exactly 1 entry per spec, got {len(manifest)}"
    )

    entry = manifest[0]
    assert isinstance(entry, dict), f"manifest[0] not a dict, got {type(entry).__name__}"
    assert entry.get("api") == "publish_file", (
        f"manifest[0].api expected 'publish_file', got {entry.get('api')!r}"
    )
    args = entry.get("args")
    assert isinstance(args, dict), "manifest[0].args must be a dict"

    src = args.get("source")
    assert src == EXPECTED_SOURCE, (
        f"manifest[0].args.source expected {EXPECTED_SOURCE!r}, got {src!r}"
    )

    dst = args.get("dest")
    assert dst == EXPECTED_DEST, (
        f"manifest[0].args.dest expected {EXPECTED_DEST!r}, got {dst!r}"
    )


if __name__ == "__main__":
    try:
        test_manifest_shape()
        print("PASS test_manifest_shape")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_shape: {e}", file=sys.stderr)
        sys.exit(1)
