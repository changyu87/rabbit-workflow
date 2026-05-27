#!/usr/bin/env python3
"""tdd-subagent: manifest declares deployment (v4.0.0 absorbed tdd-step.py).

`tdd-subagent.feature.json` declares meta-contract sections:
  - `manifest`: list of length 3 with entries (in order):
      1. {"api": "publish_agent",
          "args": {"source": "agents/tdd-subagent.md"}}
         — auto-derives dest .claude/agents/tdd-subagent.md.
      2. {"api": "publish_file",
          "args": {"source": "scripts/dispatch-tdd-subagent.py",
                   "dest": ".claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py"}}
         — explicit dest because target is not the publish_agent default.
      3. {"api": "publish_file",
          "args": {"source": "scripts/tdd-step.py",
                   "dest": ".claude/agents/tdd-subagent/scripts/tdd-step.py"}}
         — explicit dest; absorbed from tdd-state-machine at v4.0.0.
  - `runtime`: `{}` (no event hook handlers; consistent with surface.hooks=[]).
  - `configuration`: `[]` (no configurable toggles).

The manifest is the meta-contract source of truth.

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

EXPECTED_AGENT_SOURCE = "agents/tdd-subagent.md"
EXPECTED_DISPATCH_SOURCE = "scripts/dispatch-tdd-subagent.py"
EXPECTED_DISPATCH_DEST = ".claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py"
EXPECTED_STEP_SOURCE = "scripts/tdd-step.py"
EXPECTED_STEP_DEST = ".claude/agents/tdd-subagent/scripts/tdd-step.py"


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

    assert len(manifest) == 3, (
        f"manifest must have exactly 3 entries per spec, got {len(manifest)}"
    )

    # Entry 0: publish_agent for agents/tdd-subagent.md
    entry0 = manifest[0]
    assert isinstance(entry0, dict), (
        f"manifest[0] not a dict, got {type(entry0).__name__}"
    )
    assert entry0.get("api") == "publish_agent", (
        f"manifest[0].api expected 'publish_agent', got {entry0.get('api')!r}"
    )
    args0 = entry0.get("args")
    assert isinstance(args0, dict), "manifest[0].args must be a dict"
    assert args0.get("source") == EXPECTED_AGENT_SOURCE, (
        f"manifest[0].args.source expected {EXPECTED_AGENT_SOURCE!r}, "
        f"got {args0.get('source')!r}"
    )
    # publish_agent auto-derives dest; explicit dest in args is a smell.
    assert "dest" not in args0, (
        "manifest[0] (publish_agent) must not declare explicit dest; "
        "the API auto-derives .claude/agents/<basename>"
    )

    # Entry 1: publish_file for scripts/dispatch-tdd-subagent.py (explicit dest)
    entry1 = manifest[1]
    assert isinstance(entry1, dict), (
        f"manifest[1] not a dict, got {type(entry1).__name__}"
    )
    assert entry1.get("api") == "publish_file", (
        f"manifest[1].api expected 'publish_file', got {entry1.get('api')!r}"
    )
    args1 = entry1.get("args")
    assert isinstance(args1, dict), "manifest[1].args must be a dict"
    assert args1.get("source") == EXPECTED_DISPATCH_SOURCE, (
        f"manifest[1].args.source expected {EXPECTED_DISPATCH_SOURCE!r}, "
        f"got {args1.get('source')!r}"
    )
    assert args1.get("dest") == EXPECTED_DISPATCH_DEST, (
        f"manifest[1].args.dest expected {EXPECTED_DISPATCH_DEST!r}, "
        f"got {args1.get('dest')!r}"
    )

    # Entry 2: publish_file for scripts/tdd-step.py (explicit dest;
    # absorbed from retired tdd-state-machine at v4.0.0).
    entry2 = manifest[2]
    assert isinstance(entry2, dict), (
        f"manifest[2] not a dict, got {type(entry2).__name__}"
    )
    assert entry2.get("api") == "publish_file", (
        f"manifest[2].api expected 'publish_file', got {entry2.get('api')!r}"
    )
    args2 = entry2.get("args")
    assert isinstance(args2, dict), "manifest[2].args must be a dict"
    assert args2.get("source") == EXPECTED_STEP_SOURCE, (
        f"manifest[2].args.source expected {EXPECTED_STEP_SOURCE!r}, "
        f"got {args2.get('source')!r}"
    )
    assert args2.get("dest") == EXPECTED_STEP_DEST, (
        f"manifest[2].args.dest expected {EXPECTED_STEP_DEST!r}, "
        f"got {args2.get('dest')!r}"
    )


if __name__ == "__main__":
    try:
        test_manifest_shape()
        print("PASS test_manifest_shape")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_shape: {e}", file=sys.stderr)
        sys.exit(1)
