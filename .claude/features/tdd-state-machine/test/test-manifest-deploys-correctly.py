#!/usr/bin/env python3
"""Plan E.tdd-state-machine (e2e): manifest deploys tdd-step.py byte-identically.

Drives install.run_publish_loop against a temp target containing the real
contract feature plus a copy of tdd-state-machine; asserts that the
scripts/tdd-step.py source lands at
.claude/agents/tdd-subagent/scripts/tdd-step.py with matching SHA-256.

Runs in a tempdir so the scope-guard does not refuse cross-feature writes
under the real workspace.

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
FEATURE_DIR = REPO / ".claude/features/tdd-state-machine"
CONTRACT_DIR = REPO / ".claude/features/contract"

SOURCE_REL = "scripts/tdd-step.py"
DEPLOY_REL = ".claude/agents/tdd-subagent/scripts/tdd-step.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def test_manifest_deploys_tdd_step() -> None:
    install = _load_install()

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        (target / ".claude/features").mkdir(parents=True)
        shutil.copytree(CONTRACT_DIR, target / ".claude/features/contract")
        shutil.copytree(FEATURE_DIR, target / ".claude/features/tdd-state-machine")

        failures = install.run_publish_loop(str(target))
        assert failures == 0, (
            f"run_publish_loop reported {failures} failure(s) for tdd-state-machine"
        )

        src = FEATURE_DIR / SOURCE_REL
        dst = target / DEPLOY_REL
        assert dst.is_file(), f"manifest did not deploy {dst}"
        assert _sha256(src) == _sha256(dst), (
            f"deployed {dst} does not match source {src} (sha256 mismatch)"
        )


if __name__ == "__main__":
    try:
        test_manifest_deploys_tdd_step()
        print("PASS test_manifest_deploys_tdd_step")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_deploys_tdd_step: {e}", file=sys.stderr)
        sys.exit(1)
