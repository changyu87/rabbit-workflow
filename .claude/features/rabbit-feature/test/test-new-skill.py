#!/usr/bin/env python3
"""Inv 32: rabbit-feature-new SKILL.md invocation.

The SKILL.md instructs the skill to invoke new-feature.py for scaffolding
and validate-feature.py for validation. The skill is declared in
feature.json.surface.skills and in contract.md provides.skills.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the scaffolder is rewritten or replaced by a
native rabbit CLI subcommand.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SKILL_MD = FEATURE_DIR / "skills/rabbit-feature-new/SKILL.md"
FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "docs/spec/contract.md"

SCAFFOLDER_PATH = ".claude/features/rabbit-feature/scripts/new-feature.py"
VALIDATOR_PATH = ".claude/features/contract/scripts/validate-feature.py"


def test_skill_references_scaffolder() -> None:
    text = SKILL_MD.read_text()
    assert SCAFFOLDER_PATH in text, (
        f"SKILL.md must reference {SCAFFOLDER_PATH!r} for scaffolding"
    )


def test_skill_references_validator() -> None:
    text = SKILL_MD.read_text()
    assert VALIDATOR_PATH in text, (
        f"SKILL.md must reference {VALIDATOR_PATH!r} for post-scaffold validation"
    )


def test_surface_lists_skill() -> None:
    skills = json.loads(FEATURE_JSON.read_text())["surface"]["skills"]
    assert "skills/rabbit-feature-new/SKILL.md" in skills, (
        f"feature.json surface.skills must list 'skills/rabbit-feature-new/SKILL.md'; got {skills}"
    )


def test_skill_documents_plugin_mode() -> None:
    """Inv 49: SKILL.md documents both invocation forms, the plugin trigger,
    and the two-step user flow (skill + seeder dispatch)."""
    text = SKILL_MD.read_text()
    # Both invocation forms named in the skill body.
    assert "<feature-name>" in text, "SKILL.md must reference the standalone form arg"
    assert "<path-glob>" in text, "SKILL.md must document the plugin form <path-glob> arg"
    # Plugin-mode trigger named explicitly.
    assert ".rabbit/.runtime/mode" in text, (
        "SKILL.md must name the .rabbit/.runtime/mode trigger for plugin mode"
    )
    # Spec-create dispatch handoff named.
    assert "dispatch-spec-create.py" in text or "rabbit-spec-create" in text, (
        "SKILL.md must document the rabbit-spec-create dispatch handoff"
    )
    # The project-map registration target named.
    assert "project-map.json" in text, (
        "SKILL.md must name project-map.json as the plugin-mode registration target"
    )


def test_contract_provides_skill() -> None:
    text = CONTRACT_MD.read_text()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert m, "contract.md missing JSON block"
    paths = [s["path"] for s in json.loads(m.group(1))["provides"]["skills"]]
    expected = ".claude/features/rabbit-feature/skills/rabbit-feature-new/"
    assert expected in paths, (
        f"contract.md provides.skills must include {expected!r}; got {paths}"
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
