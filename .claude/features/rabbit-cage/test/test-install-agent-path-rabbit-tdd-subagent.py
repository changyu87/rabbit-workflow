#!/usr/bin/env python3
"""test-install-agent-path-rabbit-tdd-subagent.py — pin the renamed
tdd-subagent agent path in install.py's deploy closure (issue #418).

The tdd-subagent agent file was renamed:
  .claude/features/tdd-subagent/agents/tdd-subagent.md
    -> .claude/features/tdd-subagent/agents/rabbit-tdd-subagent.md
and deployed at:
  .claude/agents/tdd-subagent.md -> .claude/agents/rabbit-tdd-subagent.md

install.py must reference the NEW filename in BOTH:
  1. the AGENTS deploy mapping (source, dest tuple), and
  2. the FEATURE_INCLUDES["tdd-subagent"] agent entry.

The feature directory key ("tdd-subagent") and the dispatch script
("scripts/dispatch-tdd-subagent.py") are intentionally unchanged.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

OLD_SRC = ".claude/features/tdd-subagent/agents/tdd-subagent.md"
OLD_DST = ".claude/agents/tdd-subagent.md"
NEW_SRC = ".claude/features/tdd-subagent/agents/rabbit-tdd-subagent.md"
NEW_DST = ".claude/agents/rabbit-tdd-subagent.md"

OLD_INCLUDE = "agents/tdd-subagent.md"
NEW_INCLUDE = "agents/rabbit-tdd-subagent.md"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test_agent_path", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_agents_mapping_references_new_agent_path():
    mod = _load_install()
    assert (NEW_SRC, NEW_DST) in mod.AGENTS, (
        f"AGENTS must deploy {NEW_SRC!r} -> {NEW_DST!r}; got {mod.AGENTS}"
    )
    assert (OLD_SRC, OLD_DST) not in mod.AGENTS, (
        f"AGENTS must NOT reference the old agent path {OLD_SRC!r} -> {OLD_DST!r}"
    )
    print("PASS test_agents_mapping_references_new_agent_path")


def test_feature_includes_references_new_agent_path():
    mod = _load_install()
    entries = mod.FEATURE_INCLUDES["tdd-subagent"]
    assert NEW_INCLUDE in entries, (
        f"FEATURE_INCLUDES['tdd-subagent'] must include {NEW_INCLUDE!r}; got {entries}"
    )
    assert OLD_INCLUDE not in entries, (
        f"FEATURE_INCLUDES['tdd-subagent'] must NOT include the old {OLD_INCLUDE!r}"
    )
    print("PASS test_feature_includes_references_new_agent_path")


def test_dispatch_script_entry_unchanged():
    """The feature-dir key and dispatch script entry are intentionally
    NOT renamed — only the agent .md filename changes."""
    mod = _load_install()
    assert "tdd-subagent" in mod.FEATURE_INCLUDES, (
        "FEATURE_INCLUDES key 'tdd-subagent' must remain unchanged"
    )
    entries = mod.FEATURE_INCLUDES["tdd-subagent"]
    assert "scripts/dispatch-tdd-subagent.py" in entries, (
        "dispatch-tdd-subagent.py entry must remain unchanged"
    )
    print("PASS test_dispatch_script_entry_unchanged")


def test_new_agent_source_file_exists():
    """The renamed source agent file must exist on disk so the deploy
    mapping resolves to a real source."""
    assert (REPO / NEW_SRC).is_file(), (
        f"renamed agent source missing at {REPO / NEW_SRC}"
    )
    print("PASS test_new_agent_source_file_exists")


def main() -> int:
    test_agents_mapping_references_new_agent_path()
    test_feature_includes_references_new_agent_path()
    test_dispatch_script_entry_unchanged()
    test_new_agent_source_file_exists()
    return 0


if __name__ == "__main__":
    sys.exit(main())
