#!/usr/bin/env python3
"""Inv 40 (e2e): manifest deploys the 5 SKILL.md files byte-identically.

Drives install.run_publish_loop against a temp target containing the real
contract feature plus a copy of rabbit-feature; asserts that the 5
SKILL.md files land at .claude/skills/<name>/SKILL.md with matching
SHA-256 against the source files.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature lifecycle management is natively
    handled by Claude Code's workflow mechanism.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / "install.py"
FEATURE_DIR = REPO / ".claude/features/rabbit-feature"
CONTRACT_DIR = REPO / ".claude/features/contract"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def test_manifest_deploys_all_skills() -> None:
    install = _load_install()
    skill_dirs = sorted(d.name for d in (FEATURE_DIR / "skills").iterdir()
                        if d.is_dir())

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        (target / ".claude/features").mkdir(parents=True)
        shutil.copytree(CONTRACT_DIR, target / ".claude/features/contract")
        shutil.copytree(FEATURE_DIR, target / ".claude/features/rabbit-feature")

        failures = install.run_publish_loop(str(target))
        assert failures == 0, (
            f"run_publish_loop reported {failures} failure(s) for rabbit-feature"
        )

        for name in skill_dirs:
            src = FEATURE_DIR / "skills" / name / "SKILL.md"
            dst = target / ".claude/skills" / name / "SKILL.md"
            assert dst.is_file(), f"manifest did not deploy {dst}"
            assert _sha256(src) == _sha256(dst), (
                f"deployed {dst} does not match source {src} (sha256 mismatch)"
            )


if __name__ == "__main__":
    try:
        test_manifest_deploys_all_skills()
        print("PASS test_manifest_deploys_all_skills")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_deploys_all_skills: {e}", file=sys.stderr)
        sys.exit(1)
