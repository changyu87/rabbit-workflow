#!/usr/bin/env python3
"""Plan E.tdd-subagent (e2e): manifest deploys both targets byte-identically.

Drives install.run_publish_loop against a temp target containing the real
contract feature plus a copy of tdd-subagent; asserts that both manifest
entries land at their declared destinations with matching SHA-256:
  - agents/tdd-subagent.md -> .claude/agents/tdd-subagent.md (publish_agent)
  - scripts/dispatch-tdd-subagent.py
        -> .claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py
        (publish_file with explicit dest)

Runs in a tempdir so the scope-guard does not refuse cross-feature writes
under the real workspace.

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
FEATURE_DIR = REPO / ".claude/features/tdd-subagent"
CONTRACT_DIR = REPO / ".claude/features/contract"

AGENT_SOURCE_REL = "agents/tdd-subagent.md"
AGENT_DEPLOY_REL = ".claude/agents/tdd-subagent.md"
SCRIPT_SOURCE_REL = "scripts/dispatch-tdd-subagent.py"
SCRIPT_DEPLOY_REL = ".claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def test_manifest_deploys_both_targets() -> None:
    install = _load_install()

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        (target / ".claude/features").mkdir(parents=True)
        shutil.copytree(CONTRACT_DIR, target / ".claude/features/contract")
        shutil.copytree(FEATURE_DIR, target / ".claude/features/tdd-subagent")

        failures = install.run_publish_loop(str(target))
        assert failures == 0, (
            f"run_publish_loop reported {failures} failure(s) for tdd-subagent"
        )

        for source_rel, deploy_rel in (
            (AGENT_SOURCE_REL, AGENT_DEPLOY_REL),
            (SCRIPT_SOURCE_REL, SCRIPT_DEPLOY_REL),
        ):
            src = FEATURE_DIR / source_rel
            dst = target / deploy_rel
            assert dst.is_file(), f"manifest did not deploy {dst}"
            assert _sha256(src) == _sha256(dst), (
                f"deployed {dst} does not match source {src} (sha256 mismatch)"
            )


if __name__ == "__main__":
    try:
        test_manifest_deploys_both_targets()
        print("PASS test_manifest_deploys_both_targets")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_deploys_both_targets: {e}", file=sys.stderr)
        sys.exit(1)
