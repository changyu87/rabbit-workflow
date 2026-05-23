#!/usr/bin/env python3
"""test-install-publish-loop.py — unit tests for install.py run_publish_loop.

run_publish_loop enumerates every <target>/.claude/features/*/feature.json
manifest array and invokes each declared API via contract.lib.publish.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setup_target(td: Path) -> Path:
    """Create a target tree with the real contract feature copied in so
    install can import contract.lib.publish at run-publish-loop time."""
    target = td / "target"
    target.mkdir()
    (target / ".claude/features").mkdir(parents=True)
    shutil.copytree(
        REPO / ".claude/features/contract",
        target / ".claude/features/contract",
    )
    return target


def test_publish_loop_invokes_publish_file_and_idempotent():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        target = _setup_target(Path(td))
        fdir = target / ".claude/features/myf"
        fdir.mkdir()
        (fdir / "README-src.md").write_text("HELLO")
        (fdir / "feature.json").write_text(json.dumps({
            "name": "myf",
            "manifest": [
                {"api": "publish_file",
                 "args": {"source": "README-src.md", "dest": "README-out.md"}},
            ],
        }))
        failures = install.run_publish_loop(str(target))
        assert failures == 0
        assert (target / "README-out.md").read_text() == "HELLO"
        # second call -> still 0, idempotent no-op
        failures = install.run_publish_loop(str(target))
        assert failures == 0
    print("PASS test_publish_loop_invokes_publish_file_and_idempotent")


def test_publish_loop_reports_unknown_api_as_failure():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        target = _setup_target(Path(td))
        fdir = target / ".claude/features/bogus"
        fdir.mkdir()
        (fdir / "feature.json").write_text(json.dumps({
            "name": "bogus",
            "manifest": [
                {"api": "publish_nothing_known", "args": {}},
            ],
        }))
        failures = install.run_publish_loop(str(target))
        assert failures >= 1, f"expected failures>=1, got {failures}"
    print("PASS test_publish_loop_reports_unknown_api_as_failure")


def test_publish_loop_skips_retired_and_missing_manifest():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        target = _setup_target(Path(td))
        # Retired
        ret = target / ".claude/features/retd"; ret.mkdir()
        (ret / "feature.json").write_text(json.dumps({
            "name": "retd", "status": "retired",
            "manifest": [{"api": "publish_nothing_known"}],
        }))
        # No manifest
        nm = target / ".claude/features/nomf"; nm.mkdir()
        (nm / "feature.json").write_text(json.dumps({"name": "nomf"}))
        failures = install.run_publish_loop(str(target))
        assert failures == 0
    print("PASS test_publish_loop_skips_retired_and_missing_manifest")


def main() -> int:
    test_publish_loop_invokes_publish_file_and_idempotent()
    test_publish_loop_reports_unknown_api_as_failure()
    test_publish_loop_skips_retired_and_missing_manifest()
    return 0


if __name__ == "__main__":
    sys.exit(main())
