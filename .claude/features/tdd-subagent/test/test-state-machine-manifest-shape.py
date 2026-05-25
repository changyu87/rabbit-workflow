#!/usr/bin/env python3
"""tdd-subagent: manifest publishes tdd-step.py (Inv 44).

Spec Inv 44 requires `feature.json`'s `manifest` to contain the third entry
`{"api": "publish_file", "args": {"source": "scripts/tdd-step.py",
"dest": ".claude/agents/tdd-subagent/scripts/tdd-step.py"}}`, deploying the
absorbed state-machine script into the agent-adjacent scripts directory.

Pre-v4.0.0 this entry lived on the retired `tdd-state-machine` feature's
manifest as a cross-feature publish_file; post-absorption the source path
is intra-feature.

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


def test_tdd_step_manifest_entry() -> None:
    data = json.loads(FEATURE_JSON.read_text())

    manifest = data.get("manifest", [])
    assert isinstance(manifest, list), (
        f"manifest must be list, got {type(manifest).__name__}"
    )

    # Inv 44 anchors the entry to position 2 (the third entry) — the
    # publish_file for tdd-step.py with explicit dest.
    matches = [
        e for e in manifest
        if isinstance(e, dict)
        and e.get("api") == "publish_file"
        and isinstance(e.get("args"), dict)
        and e["args"].get("source") == EXPECTED_SOURCE
    ]
    assert len(matches) == 1, (
        f"manifest must declare exactly one publish_file entry for "
        f"{EXPECTED_SOURCE!r}, found {len(matches)}"
    )
    entry = matches[0]
    args = entry["args"]
    assert args.get("dest") == EXPECTED_DEST, (
        f"publish_file entry for {EXPECTED_SOURCE!r}: dest expected "
        f"{EXPECTED_DEST!r}, got {args.get('dest')!r}"
    )


if __name__ == "__main__":
    try:
        test_tdd_step_manifest_entry()
        print("PASS test_tdd_step_manifest_entry")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_tdd_step_manifest_entry: {e}", file=sys.stderr)
        sys.exit(1)
