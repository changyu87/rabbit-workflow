#!/usr/bin/env python3
"""Plan E.tdd-subagent (e2e): manifest deploys all three targets byte-identically.

Drives install.run_publish_loop against a temp target containing the real
contract feature plus a copy of tdd-subagent; asserts that all three manifest
entries land at their declared destinations with matching SHA-256:
  - agents/rabbit-tdd-subagent.md -> .claude/agents/rabbit-tdd-subagent.md (publish_agent)
  - scripts/dispatch-tdd-subagent.py
        -> .claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py
        (publish_file with explicit dest)
  - scripts/tdd-step.py
        -> .claude/agents/tdd-subagent/scripts/tdd-step.py
        (publish_file with explicit dest; absorbed from tdd-state-machine at v4.0.0)

Runs in a tempdir so the scope-guard does not refuse cross-feature writes
under the real workspace.

Version: 1.1.0
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
FEATURE_DIR = REPO / ".claude/features/tdd-subagent"
CONTRACT_DIR = REPO / ".claude/features/contract"

AGENT_SOURCE_REL = "agents/rabbit-tdd-subagent.md"
AGENT_DEPLOY_REL = ".claude/agents/rabbit-tdd-subagent.md"
DISPATCH_SOURCE_REL = "scripts/dispatch-tdd-subagent.py"
DISPATCH_DEPLOY_REL = ".claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py"
STEP_SOURCE_REL = "scripts/tdd-step.py"
STEP_DEPLOY_REL = ".claude/agents/tdd-subagent/scripts/tdd-step.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def test_manifest_deploys_all_targets() -> None:
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
            (DISPATCH_SOURCE_REL, DISPATCH_DEPLOY_REL),
            (STEP_SOURCE_REL, STEP_DEPLOY_REL),
        ):
            src = FEATURE_DIR / source_rel
            dst = target / deploy_rel
            assert dst.is_file(), f"manifest did not deploy {dst}"
            assert _sha256(src) == _sha256(dst), (
                f"deployed {dst} does not match source {src} (sha256 mismatch)"
            )


if __name__ == "__main__":
    try:
        test_manifest_deploys_all_targets()
        print("PASS test_manifest_deploys_all_targets")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_manifest_deploys_all_targets: {e}", file=sys.stderr)
        sys.exit(1)
