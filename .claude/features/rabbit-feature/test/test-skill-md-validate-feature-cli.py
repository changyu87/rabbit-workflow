#!/usr/bin/env python3
"""E2E test for RABBIT-FEATURE-BUG-4 (SKILL.md invocation snippets).

The rabbit-feature-new and rabbit-feature-audit skills must reference the
runnable CLI shim `validate-feature.py` (a real script that exists and
works) — NOT the broken `from importlib import import_module ...
import_module('claude.features.contract.lib.checks')` snippet, which fails
because `claude.features.contract.lib.checks` is not an importable dotted
path from any cwd a normal caller would be in.

Both SKILL.md files documented `validate_feature` via the broken snippet;
this test locks them to the working CLI form and prevents regression.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When the contract feature exposes validate_feature
as a first-class CLI under its own well-known entry point and both
SKILL.md files have been migrated to that entry point.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_NEW = REPO_ROOT / ".claude/features/rabbit-feature/skills/rabbit-feature-new/SKILL.md"
SKILL_AUDIT = REPO_ROOT / ".claude/features/rabbit-feature/skills/rabbit-feature-audit/SKILL.md"
VALIDATE_CLI = REPO_ROOT / ".claude/features/contract/scripts/validate-feature.py"

CLI_TOKEN = ".claude/features/contract/scripts/validate-feature.py"
BROKEN_TOKEN = "import_module"


def test_validate_cli_exists() -> None:
    assert VALIDATE_CLI.is_file(), (
        f"validate-feature.py CLI shim missing at {VALIDATE_CLI}; "
        "the SKILL.md snippets depend on it."
    )


def test_skill_new_uses_cli() -> None:
    text = SKILL_NEW.read_text()
    assert CLI_TOKEN in text, (
        f"rabbit-feature-new SKILL.md must reference the runnable CLI "
        f"shim path {CLI_TOKEN!r}"
    )


def test_skill_new_drops_broken_import_module() -> None:
    text = SKILL_NEW.read_text()
    assert BROKEN_TOKEN not in text, (
        "rabbit-feature-new SKILL.md still contains the broken "
        "`import_module` snippet; replace it with a validate-feature.py CLI call."
    )


def test_skill_audit_uses_cli() -> None:
    text = SKILL_AUDIT.read_text()
    assert CLI_TOKEN in text, (
        f"rabbit-feature-audit SKILL.md must reference the runnable CLI "
        f"shim path {CLI_TOKEN!r}"
    )


def test_skill_audit_drops_broken_import_module() -> None:
    text = SKILL_AUDIT.read_text()
    assert BROKEN_TOKEN not in text, (
        "rabbit-feature-audit SKILL.md still contains the broken "
        "`import_module` snippet; replace it with a validate-feature.py CLI call."
    )


def main() -> int:
    tests = [
        test_validate_cli_exists,
        test_skill_new_uses_cli,
        test_skill_new_drops_broken_import_module,
        test_skill_audit_uses_cli,
        test_skill_audit_drops_broken_import_module,
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
