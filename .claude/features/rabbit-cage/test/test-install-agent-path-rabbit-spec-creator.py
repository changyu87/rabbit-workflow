#!/usr/bin/env python3
"""test-install-agent-path-rabbit-spec-creator.py — pin the renamed
rabbit-spec drafting agent path in install.py's deploy closure (issue #477).

The rabbit-spec drafting agent file was renamed (issues #471/#473):
  .claude/features/rabbit-spec/agents/spec-creator.md
    -> .claude/features/rabbit-spec/agents/rabbit-spec-creator.md
and deployed at:
  .claude/agents/spec-creator.md -> .claude/agents/rabbit-spec-creator.md

install.py must reference the NEW filename in BOTH:
  1. the AGENTS deploy mapping (source, dest tuple), and
  2. the FEATURE_INCLUDES["rabbit-spec"] agent entry.

The feature directory key ("rabbit-spec") and the dispatch script
("scripts/dispatch-spec-create.py") are intentionally unchanged.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"

OLD_SRC = ".claude/features/rabbit-spec/agents/spec-creator.md"
OLD_DST = ".claude/agents/spec-creator.md"
NEW_SRC = ".claude/features/rabbit-spec/agents/rabbit-spec-creator.md"
NEW_DST = ".claude/agents/rabbit-spec-creator.md"

OLD_INCLUDE = "agents/spec-creator.md"
NEW_INCLUDE = "agents/rabbit-spec-creator.md"


def _load_install():
    spec = importlib.util.spec_from_file_location(
        "install_under_test_spec_creator_path", INSTALL_PY
    )
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
    entries = mod.FEATURE_INCLUDES["rabbit-spec"]
    assert NEW_INCLUDE in entries, (
        f"FEATURE_INCLUDES['rabbit-spec'] must include {NEW_INCLUDE!r}; got {entries}"
    )
    assert OLD_INCLUDE not in entries, (
        f"FEATURE_INCLUDES['rabbit-spec'] must NOT include the old {OLD_INCLUDE!r}"
    )
    print("PASS test_feature_includes_references_new_agent_path")


def test_dispatch_script_entry_unchanged():
    """The feature-dir key and dispatch script entry are intentionally
    NOT renamed — only the agent .md filename changes."""
    mod = _load_install()
    assert "rabbit-spec" in mod.FEATURE_INCLUDES, (
        "FEATURE_INCLUDES key 'rabbit-spec' must remain unchanged"
    )
    entries = mod.FEATURE_INCLUDES["rabbit-spec"]
    assert "scripts/dispatch-spec-create.py" in entries, (
        "dispatch-spec-create.py entry must remain unchanged"
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
