#!/usr/bin/env python3
"""Inv 39: surface and contract consistency.

(a) Every skill listed in `feature.json.surface.skills` has a corresponding
    entry under `contract.md.provides.skills`.
(b) Every cross-feature file or script that this feature's code reads or
    invokes has a corresponding entry under `contract.md.reads.files` or
    `contract.md.invokes.scripts`.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when a machine-readable surface/reads validator is
wired into the contract feature.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "specs/contract.md"
SCRIPTS_DIR = FEATURE_DIR / "scripts"


def _contract_block() -> dict:
    text = CONTRACT_MD.read_text()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert m, "contract.md missing JSON block"
    return json.loads(m.group(1))


def _skill_dir(rel_path: str) -> str:
    # "skills/rabbit-feature-touch/SKILL.md" -> ".claude/features/rabbit-feature/skills/rabbit-feature-touch/"
    return f".claude/features/rabbit-feature/{rel_path.rsplit('/', 1)[0]}/"


def test_every_surface_skill_in_contract_provides() -> None:
    skills = json.loads(FEATURE_JSON.read_text())["surface"]["skills"]
    contract = _contract_block()
    provided = {s["path"] for s in contract["provides"]["skills"]}
    missing = [_skill_dir(s) for s in skills if _skill_dir(s) not in provided]
    assert not missing, (
        f"contract.md provides.skills missing entries for surface.skills: {missing}"
    )


def test_cross_feature_scripts_in_invokes() -> None:
    """Scripts under scripts/ that shell-invoke other features' scripts
    must have those other-feature paths declared in contract.md
    invokes.scripts."""
    contract = _contract_block()
    invoked = {s["path"] for s in contract.get("invokes", {}).get("scripts", [])}

    expected_paths: set[str] = set()
    for script_path in SCRIPTS_DIR.glob("*.py"):
        text = script_path.read_text()
        # Look for hardcoded references to other features' scripts.
        for m in re.finditer(
            r"\.claude/features/(?!rabbit-feature/)[^/]+/scripts/[\w\-]+\.py",
            text,
        ):
            expected_paths.add(m.group(0))

    missing = sorted(expected_paths - invoked)
    assert not missing, (
        f"contract.md invokes.scripts missing entries for cross-feature "
        f"scripts referenced by this feature's scripts: {missing}"
    )


if __name__ == "__main__":
    tests = [
        test_every_surface_skill_in_contract_provides,
        test_cross_feature_scripts_in_invokes,
    ]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
