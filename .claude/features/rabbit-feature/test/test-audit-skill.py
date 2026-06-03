#!/usr/bin/env python3
"""Inv 34-35: rabbit-feature-audit SKILL.md.

Covers invocation surface ('all' / '<feature-name>'), validate-feature.py
invocation, and surface/contract declarations.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when contract.lib.checks.validate_feature is
exposed via a first-class CLI in the contract feature.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SKILL_MD = FEATURE_DIR / "skills/rabbit-feature-audit/SKILL.md"
FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "docs/contract.md"

VALIDATOR_PATH = ".claude/features/contract/scripts/validate-feature.py"


# Inv 34: invocation surface — 'all' and '<feature-name>'
def test_inv34_documents_all_mode() -> None:
    text = SKILL_MD.read_text()
    assert "all" in text, "SKILL.md must document the 'all' args mode"


def test_inv34_documents_single_feature_mode() -> None:
    text = SKILL_MD.read_text()
    assert "<feature-name>" in text or "feature-name" in text, (
        "SKILL.md must document the single '<feature-name>' args mode"
    )


# Inv 35: validate-feature.py invocation
def test_inv35_skill_references_validator() -> None:
    text = SKILL_MD.read_text()
    assert VALIDATOR_PATH in text, (
        f"SKILL.md must reference {VALIDATOR_PATH!r} for per-feature validation"
    )


def test_inv35_skill_emits_pass_fail() -> None:
    text = SKILL_MD.read_text().lower()
    assert "pass" in text and "fail" in text, (
        "SKILL.md must document per-feature pass/fail output"
    )


def test_surface_lists_skill() -> None:
    skills = json.loads(FEATURE_JSON.read_text())["surface"]["skills"]
    assert "skills/rabbit-feature-audit/SKILL.md" in skills, (
        f"feature.json surface.skills must list 'skills/rabbit-feature-audit/SKILL.md'; got {skills}"
    )


def test_contract_provides_skill() -> None:
    text = CONTRACT_MD.read_text()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert m, "contract.md missing JSON block"
    paths = [s["path"] for s in json.loads(m.group(1))["provides"]["skills"]]
    expected = ".claude/features/rabbit-feature/skills/rabbit-feature-audit/"
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
