#!/usr/bin/env python3
"""Plan E.rabbit-file (e2e): manifest deploys the rabbit-file SKILL.md byte-identically.

Drives install.run_publish_loop against a temp target containing the real
contract feature plus a copy of rabbit-file; asserts that the
skills/rabbit-file/SKILL.md source lands at
.claude/skills/rabbit-file/SKILL.md with matching SHA-256.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when publish.json is removed (Plan F) and only
    the manifest path remains.
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
FEATURE_DIR = REPO / ".claude/features/rabbit-file"
CONTRACT_DIR = REPO / ".claude/features/contract"

SKILL_REL = "skills/rabbit-file/SKILL.md"
DEPLOY_REL = ".claude/skills/rabbit-file/SKILL.md"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def test_manifest_deploys_rabbit_file_skill() -> None:
    install = _load_install()

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        (target / ".claude/features").mkdir(parents=True)
        shutil.copytree(CONTRACT_DIR, target / ".claude/features/contract")
        shutil.copytree(FEATURE_DIR, target / ".claude/features/rabbit-file")

        failures = install.run_publish_loop(str(target))
        assert failures == 0, (
            f"run_publish_loop reported {failures} failure(s) for rabbit-file"
        )

        src = FEATURE_DIR / SKILL_REL
        dst = target / DEPLOY_REL
        assert dst.is_file(), f"manifest did not deploy {dst}"
        assert _sha256(src) == _sha256(dst), (
            f"deployed {dst} does not match source {src} (sha256 mismatch)"
        )


if __name__ == "__main__":
    try:
        test_manifest_deploys_rabbit_file_skill()
        print("PASS test_manifest_deploys_rabbit_file_skill")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_deploys_rabbit_file_skill: {e}", file=sys.stderr)
        sys.exit(1)
