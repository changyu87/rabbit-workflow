#!/usr/bin/env python3
"""E2E test for RABBIT-FEATURE-BUG-4 (cross-feature dependency declarations).

The rabbit-feature-new skill shells out to rabbit-cage's new-feature.py
(Inv 33 + spec narrative), and both the -new and -audit skills depend on
contract.lib.checks (Inv 33/34). Per the Bounded Scope philosophy, these
cross-feature dependencies must be declared in contract.md so consumers can
see the boundary contract without reading the SKILL.md prose.

Locks:
- contract.md `invokes.scripts` includes
  `.claude/features/rabbit-cage/scripts/new-feature.py`.
- contract.md `reads.files` includes
  `.claude/features/contract/lib/checks.py`.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When new-feature.py is moved into this feature (the
invokes entry disappears with the cross-feature boundary) AND when the
contract library entry path stops being load-bearing for this feature.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_MD = REPO_ROOT / ".claude/features/rabbit-feature/docs/spec/contract.md"

NEW_FEATURE_SCRIPT = ".claude/features/rabbit-cage/scripts/new-feature.py"
CHECKS_LIB_PATH = ".claude/features/contract/lib/checks.py"


def _contract_block() -> dict:
    text = CONTRACT_MD.read_text()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert m, "contract.md missing JSON block"
    return json.loads(m.group(1))


def test_invokes_scripts_lists_new_feature_script() -> None:
    data = _contract_block()
    paths = [s.get("path", "") for s in data.get("invokes", {}).get("scripts", [])]
    assert NEW_FEATURE_SCRIPT in paths, (
        f"contract.md invokes.scripts must list {NEW_FEATURE_SCRIPT!r} "
        f"(rabbit-feature-new shells out to it per Inv 33); got {paths}"
    )


def test_reads_files_lists_checks_lib() -> None:
    data = _contract_block()
    paths = data.get("reads", {}).get("files", [])
    assert CHECKS_LIB_PATH in paths, (
        f"contract.md reads.files must list {CHECKS_LIB_PATH!r} "
        f"(rabbit-feature-new and rabbit-feature-audit depend on validate_feature); "
        f"got {paths}"
    )


def main() -> int:
    tests = [
        test_invokes_scripts_lists_new_feature_script,
        test_reads_files_lists_checks_lib,
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
