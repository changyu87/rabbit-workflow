#!/usr/bin/env python3
"""E2E regression test for RABBIT-FEATURE-BUG-2 (surface/reads drift).

Asserts that:
  1. `feature.json` `surface.skills` lists the published
     `skills/rabbit-feature-touch/SKILL.md`.
  2. `docs/spec/contract.md` `reads.files` declares the
     `.claude/features/contract/build-contract.json` file that the Inv 4
     test reads at runtime.

Both omissions were the drift fixed by RABBIT-FEATURE-BUG-2: the feature
publishes a skill and reads a cross-feature contract file without
declaring either in its machine-first metadata.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When a machine-readable surface/reads validator is
wired into the contract feature.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "docs/spec/contract.md"

EXPECTED_SKILL_PATH = "skills/rabbit-feature-touch/SKILL.md"
EXPECTED_READ_PATH = ".claude/features/contract/build-contract.json"


def _load_contract_json() -> dict:
    text = CONTRACT_MD.read_text()
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert match, f"no fenced JSON block in {CONTRACT_MD}"
    return json.loads(match.group(1))


def test_feature_json_surface_skills_lists_rabbit_feature_touch() -> None:
    data = json.loads(FEATURE_JSON.read_text())
    skills = data.get("surface", {}).get("skills", [])
    assert EXPECTED_SKILL_PATH in skills, (
        f"feature.json surface.skills missing {EXPECTED_SKILL_PATH!r}; "
        f"got {skills!r}"
    )


def test_contract_md_reads_files_lists_build_contract() -> None:
    contract = _load_contract_json()
    reads_files = contract.get("reads", {}).get("files", [])
    assert EXPECTED_READ_PATH in reads_files, (
        f"contract.md reads.files missing {EXPECTED_READ_PATH!r}; "
        f"got {reads_files!r}"
    )


def main() -> int:
    tests = [
        test_feature_json_surface_skills_lists_rabbit_feature_touch,
        test_contract_md_reads_files_lists_build_contract,
    ]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
