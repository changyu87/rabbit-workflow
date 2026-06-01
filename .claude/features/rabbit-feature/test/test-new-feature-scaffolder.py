#!/usr/bin/env python3
"""Inv 33: scaffold-feature.py scaffolds a conforming feature dir.

The scaffolder is executable and produces a directory containing feature.json
(with template_version), docs/spec/spec.md, docs/spec/contract.md, and
test/run.py (no test/run.sh). The scaffolded directory passes
validate-feature.py immediately.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the scaffolder is rewritten or replaced.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
NEW_FEATURE = REPO_ROOT / ".claude/features/rabbit-feature/scripts/scaffold-feature.py"
VALIDATE = REPO_ROOT / ".claude/features/contract/scripts/validate-feature.py"


def test_executable() -> None:
    assert NEW_FEATURE.is_file(), f"missing scaffolder: {NEW_FEATURE}"
    assert os.access(NEW_FEATURE, os.X_OK), "scaffold-feature.py must be executable"


def test_scaffolds_conforming_dir() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-scaffold-") as tmp:
        env = dict(os.environ)
        env["RABBIT_ROOT"] = str(REPO_ROOT)
        res = subprocess.run(
            [sys.executable, str(NEW_FEATURE), tmp, "demo-feature",
             "--owner", "scaffolder-test", "--description", "demo"],
            env=env, capture_output=True, text=True,
        )
        assert res.returncode == 0, (
            f"scaffolder exited {res.returncode}; stderr={res.stderr!r}"
        )
        feature_dir = Path(tmp) / "demo-feature"
        assert (feature_dir / "feature.json").is_file(), "scaffold missing feature.json"
        assert (feature_dir / "docs/spec/spec.md").is_file(), "scaffold missing docs/spec/spec.md"
        assert (feature_dir / "docs/spec/contract.md").is_file(), (
            "scaffold missing docs/spec/contract.md"
        )
        assert (feature_dir / "test/run.py").is_file(), "scaffold missing test/run.py"
        assert not (feature_dir / "test/run.sh").exists(), (
            "scaffold must NOT create test/run.sh (Python-only stack)"
        )
        data = json.loads((feature_dir / "feature.json").read_text())
        assert data.get("template_version"), "feature.json must declare template_version"

        # Scaffold must pass validate-feature.py immediately.
        vres = subprocess.run(
            [sys.executable, str(VALIDATE), str(feature_dir)],
            capture_output=True, text=True,
        )
        assert vres.returncode == 0, (
            f"validate-feature.py rc={vres.returncode}; stderr={vres.stderr!r}; "
            f"stdout={vres.stdout!r}"
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
