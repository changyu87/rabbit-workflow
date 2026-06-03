#!/usr/bin/env python3
"""issue #399 Phase 2: rabbit-feature's own spec dir migrated to specs/.

End-to-end check of the rabbit-feature feature directory layout after the
docs/spec/ -> specs/ migration:

  * specs/spec.md and specs/contract.md exist and are non-empty.
  * The legacy docs/spec/ directory is gone.
  * docs/bugs/ is retained (only docs/spec was moved, not all of docs/).
  * The feature still passes validate-feature.py (which dual-reads
    specs/ then docs/spec/).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when every rabbit feature has migrated off the legacy
docs/spec/ layout and the dual-read fallback is removed (issue #399 cleanup).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
VALIDATE = REPO_ROOT / ".claude/features/contract/scripts/validate-feature.py"


def test_specs_dir_exists() -> None:
    spec_md = FEATURE_DIR / "specs/spec.md"
    contract_md = FEATURE_DIR / "specs/contract.md"
    assert spec_md.is_file(), f"missing {spec_md}"
    assert contract_md.is_file(), f"missing {contract_md}"
    assert spec_md.read_text().strip(), "specs/spec.md is empty"
    assert contract_md.read_text().strip(), "specs/contract.md is empty"


def test_legacy_docs_spec_gone() -> None:
    legacy = FEATURE_DIR / "docs/spec"
    assert not legacy.exists(), (
        f"legacy docs/spec/ must be gone after migration (issue #399); found {legacy}"
    )


def test_docs_bugs_retained() -> None:
    bugs = FEATURE_DIR / "docs/bugs"
    assert bugs.is_dir(), (
        f"docs/bugs/ must be retained — only docs/spec was moved, not all of docs/; "
        f"missing {bugs}"
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
