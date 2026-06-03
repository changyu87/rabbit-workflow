#!/usr/bin/env python3
"""issue #399 Phase 2b: rabbit-feature's own doc artifacts live at flat docs/.

End-to-end check of the rabbit-feature feature directory layout after the
specs/ -> flat docs/ migration:

  * docs/spec.md, docs/contract.md and docs/CHANGELOG.md exist and are
    non-empty.
  * docs/bugs/ is retained (the doc artifacts moved as siblings of bugs/,
    not nested under it).
  * The legacy specs/ directory is gone.
  * The legacy root-level CHANGELOG.md is gone (moved into docs/).
  * The feature still passes validate-feature.py (which dual-reads flat
    docs/ then specs/ then docs/spec/).

Version: 2.0.0
Owner: rabbit-workflow team
Deprecation criterion: when every rabbit feature has migrated to the flat
docs/ layout and the dual-read fallback is removed (issue #399 cleanup).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
VALIDATE = REPO_ROOT / ".claude/features/contract/scripts/validate-feature.py"


def test_flat_docs_exist() -> None:
    spec_md = FEATURE_DIR / "docs/spec.md"
    contract_md = FEATURE_DIR / "docs/contract.md"
    changelog_md = FEATURE_DIR / "docs/CHANGELOG.md"
    assert spec_md.is_file(), f"missing {spec_md}"
    assert contract_md.is_file(), f"missing {contract_md}"
    assert changelog_md.is_file(), f"missing {changelog_md}"
    assert spec_md.read_text().strip(), "docs/spec.md is empty"
    assert contract_md.read_text().strip(), "docs/contract.md is empty"
    assert changelog_md.read_text().strip(), "docs/CHANGELOG.md is empty"


def test_docs_bugs_retained() -> None:
    bugs = FEATURE_DIR / "docs/bugs"
    assert bugs.is_dir(), (
        f"docs/bugs/ must be retained — doc artifacts moved as siblings, not "
        f"nested under bugs/; missing {bugs}"
    )


def test_legacy_specs_gone() -> None:
    legacy = FEATURE_DIR / "specs"
    assert not legacy.exists(), (
        f"legacy specs/ must be gone after the flat-docs migration (issue "
        f"#399 Phase 2b); found {legacy}"
    )


def test_legacy_root_changelog_gone() -> None:
    legacy = FEATURE_DIR / "CHANGELOG.md"
    assert not legacy.exists(), (
        f"root-level CHANGELOG.md must be gone after the flat-docs migration "
        f"(moved into docs/); found {legacy}"
    )


def test_feature_still_validates() -> None:
    res = subprocess.run(
        [sys.executable, str(VALIDATE), str(FEATURE_DIR)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, (
        f"validate-feature.py rc={res.returncode}; stderr={res.stderr!r}; "
        f"stdout={res.stdout!r}"
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
