#!/usr/bin/env python3
"""E2E test for rabbit-feature absorption of rabbit-feature-scope.

Asserts the absorbed surface is materialized inside rabbit-feature:

  1. skills/rabbit-feature-scope/SKILL.md exists and is byte-identical to
     the source in rabbit-feature-scope (byte-identical absorption).
  2. scripts/resolve-scope.py exists, is executable, byte-identical to source.
  3. scripts/format-feature-context.py exists, is executable, byte-identical
     to source.
  4. The absorbed test files exist in test/ alongside the existing suite.
  5. feature.json surface declares the absorbed skill and scripts.
  6. contract.md provides.skills and provides.scripts declare the new surface.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When rabbit-feature-scope feature dir is deleted
(separate cleanup cycle) and the byte-identical source comparison is no
longer meaningful.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = FEATURE_DIR.parents[2]
SOURCE_SCOPE_DIR = REPO_ROOT / ".claude/features/rabbit-feature-scope"

ABSORBED_SKILL = FEATURE_DIR / "skills/rabbit-feature-scope/SKILL.md"
ABSORBED_RESOLVE = FEATURE_DIR / "scripts/resolve-scope.py"
ABSORBED_FORMAT = FEATURE_DIR / "scripts/format-feature-context.py"

SOURCE_SKILL = SOURCE_SCOPE_DIR / "skills/rabbit-feature-scope/SKILL.md"
SOURCE_RESOLVE = SOURCE_SCOPE_DIR / "scripts/resolve-scope.py"
SOURCE_FORMAT = SOURCE_SCOPE_DIR / "scripts/format-feature-context.py"

FEATURE_JSON = FEATURE_DIR / "feature.json"
CONTRACT_MD = FEATURE_DIR / "docs/spec/contract.md"


def _load_contract_json() -> dict:
    text = CONTRACT_MD.read_text()
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert match, f"no fenced JSON block in {CONTRACT_MD}"
    return json.loads(match.group(1))


def test_absorbed_skill_exists_and_byte_identical() -> None:
    assert ABSORBED_SKILL.is_file(), f"missing absorbed skill: {ABSORBED_SKILL}"
    assert SOURCE_SKILL.is_file(), f"missing source skill: {SOURCE_SKILL}"
    assert ABSORBED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes(), (
        f"absorbed SKILL.md differs from source\n"
        f"  source:   {SOURCE_SKILL}\n"
        f"  absorbed: {ABSORBED_SKILL}"
    )


def test_absorbed_resolve_scope_exists_executable_byte_identical() -> None:
    assert ABSORBED_RESOLVE.is_file(), f"missing absorbed script: {ABSORBED_RESOLVE}"
    assert os.access(ABSORBED_RESOLVE, os.X_OK), (
        f"absorbed resolve-scope.py not executable: {ABSORBED_RESOLVE}"
    )
    assert SOURCE_RESOLVE.is_file(), f"missing source script: {SOURCE_RESOLVE}"
    assert ABSORBED_RESOLVE.read_bytes() == SOURCE_RESOLVE.read_bytes(), (
        f"absorbed resolve-scope.py differs from source"
    )


def test_absorbed_format_context_exists_executable_byte_identical() -> None:
    assert ABSORBED_FORMAT.is_file(), f"missing absorbed script: {ABSORBED_FORMAT}"
    assert os.access(ABSORBED_FORMAT, os.X_OK), (
        f"absorbed format-feature-context.py not executable: {ABSORBED_FORMAT}"
    )
    assert SOURCE_FORMAT.is_file(), f"missing source script: {SOURCE_FORMAT}"
    assert ABSORBED_FORMAT.read_bytes() == SOURCE_FORMAT.read_bytes(), (
        f"absorbed format-feature-context.py differs from source"
    )


def test_feature_json_surface_declares_absorbed_skill_and_scripts() -> None:
    data = json.loads(FEATURE_JSON.read_text())
    skills = data.get("surface", {}).get("skills", [])
    scripts = data.get("surface", {}).get("scripts", [])
    assert "skills/rabbit-feature-scope/SKILL.md" in skills, (
        f"feature.json surface.skills missing absorbed skill; got {skills!r}"
    )
    assert "scripts/resolve-scope.py" in scripts, (
        f"feature.json surface.scripts missing resolve-scope.py; got {scripts!r}"
    )
    assert "scripts/format-feature-context.py" in scripts, (
        f"feature.json surface.scripts missing format-feature-context.py; "
        f"got {scripts!r}"
    )


def test_absorbed_test_files_copied() -> None:
    """Every test-*.py from rabbit-feature-scope/test/ is present in
    rabbit-feature/test/ (byte-identical absorption, per impl-suggestion)."""
    source_tests = sorted(
        p for p in (SOURCE_SCOPE_DIR / "test").glob("test-*.py")
    )
    assert source_tests, (
        f"no source tests found under {SOURCE_SCOPE_DIR / 'test'}"
    )
    missing = []
    for src in source_tests:
        dst = FEATURE_DIR / "test" / src.name
        if not dst.is_file():
            missing.append(src.name)
    assert not missing, (
        f"absorbed test files missing in rabbit-feature/test/: {missing}"
    )


def test_contract_md_provides_declares_absorbed_surface() -> None:
    contract = _load_contract_json()
    provides = contract.get("provides", {})
    skill_paths = [s.get("path", "") for s in provides.get("skills", [])]
    script_paths = [s.get("path", "") for s in provides.get("scripts", [])]
    assert any(
        "rabbit-feature-scope" in p for p in skill_paths
    ), f"contract.md provides.skills missing rabbit-feature-scope; got {skill_paths!r}"
    assert any(
        "resolve-scope.py" in p for p in script_paths
    ), f"contract.md provides.scripts missing resolve-scope.py; got {script_paths!r}"
    assert any(
        "format-feature-context.py" in p for p in script_paths
    ), (
        f"contract.md provides.scripts missing format-feature-context.py; "
        f"got {script_paths!r}"
    )


TESTS = [
    test_absorbed_skill_exists_and_byte_identical,
    test_absorbed_resolve_scope_exists_executable_byte_identical,
    test_absorbed_format_context_exists_executable_byte_identical,
    test_absorbed_test_files_copied,
    test_feature_json_surface_declares_absorbed_skill_and_scripts,
    test_contract_md_provides_declares_absorbed_surface,
]


def main() -> int:
    failures: list[str] = []
    for test in TESTS:
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
