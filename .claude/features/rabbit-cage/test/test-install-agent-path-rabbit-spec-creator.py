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

The agent is KEPT — only its filename changed. Issue #922 (piece 3/5)
additionally retired the rabbit-spec-create SKILL wrapper and renamed the
dispatch input assembler script, so this test also pins the post-#922 truth
for the rabbit-spec surface in install.py:
  - the rabbit-spec-create SKILL.md appears NOWHERE in install.py's closure
    (neither SKILLS nor FEATURE_INCLUDES["rabbit-spec"]);
  - FEATURE_INCLUDES["rabbit-spec"] lists the RENAMED dispatch script
    "scripts/dispatch-spec-creator.py" (NOT the old "dispatch-spec-create.py");
  - the rabbit-spec-creator AGENT remains deployed.
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


def test_dispatch_script_renamed_in_feature_includes():
    """#922: the dispatch input assembler was renamed
    dispatch-spec-create.py -> dispatch-spec-creator.py. The feature-dir key
    ('rabbit-spec') is unchanged; the script entry tracks the NEW name."""
    mod = _load_install()
    assert "rabbit-spec" in mod.FEATURE_INCLUDES, (
        "FEATURE_INCLUDES key 'rabbit-spec' must remain unchanged"
    )
    entries = mod.FEATURE_INCLUDES["rabbit-spec"]
    assert "scripts/dispatch-spec-creator.py" in entries, (
        "FEATURE_INCLUDES['rabbit-spec'] must list the RENAMED "
        f"'scripts/dispatch-spec-creator.py'; got {entries}"
    )
    assert "scripts/dispatch-spec-create.py" not in entries, (
        "FEATURE_INCLUDES['rabbit-spec'] must NOT list the old "
        "'scripts/dispatch-spec-create.py' (renamed by #922)"
    )
    print("PASS test_dispatch_script_renamed_in_feature_includes")


def test_rabbit_spec_create_skill_fully_retired():
    """#922 piece 3/5: the rabbit-spec-create SKILL wrapper is retired. It must
    appear NOWHERE in install.py's closure — neither the SKILLS deploy mapping
    nor FEATURE_INCLUDES['rabbit-spec']."""
    mod = _load_install()
    skill_src = ".claude/features/rabbit-spec/skills/rabbit-spec-create/SKILL.md"
    skill_dst = ".claude/skills/rabbit-spec-create/SKILL.md"
    for src, dst in mod.SKILLS:
        assert "rabbit-spec-create" not in src, (
            f"SKILLS still references retired rabbit-spec-create skill: {(src, dst)}"
        )
    assert (skill_src, skill_dst) not in mod.SKILLS, (
        "SKILLS must NOT deploy the retired rabbit-spec-create skill"
    )
    entries = mod.FEATURE_INCLUDES["rabbit-spec"]
    assert "skills/rabbit-spec-create/SKILL.md" not in entries, (
        "FEATURE_INCLUDES['rabbit-spec'] must NOT list the retired "
        f"rabbit-spec-create skill; got {entries}"
    )
    # The rabbit-spec-update skill is unaffected — still deployed.
    assert "skills/rabbit-spec-update/SKILL.md" in entries, (
        "FEATURE_INCLUDES['rabbit-spec'] must still list rabbit-spec-update"
    )
    print("PASS test_rabbit_spec_create_skill_fully_retired")


def test_new_agent_source_file_exists():
    """The renamed source agent file must exist on disk so the deploy
    mapping resolves to a real source. The agent is KEPT by #922."""
    assert (REPO / NEW_SRC).is_file(), (
        f"renamed agent source missing at {REPO / NEW_SRC}"
    )
    print("PASS test_new_agent_source_file_exists")


def main() -> int:
    test_agents_mapping_references_new_agent_path()
    test_feature_includes_references_new_agent_path()
    test_dispatch_script_renamed_in_feature_includes()
    test_rabbit_spec_create_skill_fully_retired()
    test_new_agent_source_file_exists()
    return 0


if __name__ == "__main__":
    sys.exit(main())
