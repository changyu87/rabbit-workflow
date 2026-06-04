#!/usr/bin/env python3
"""test-install-deploys-check-release-update.py — e2e (issue #605).

Runs the REAL installer (`install.main(--src --target)`) against a source
tree built from install.py's declared closure, then asserts the contract
release-update probe `scripts/check-release-update.py` actually lands in the
deployed `<target>/.claude/features/contract/scripts/` directory.

This reproduces the bug end-to-end: contract's `check_release_update`
runtime API (SessionStart) and the `/rabbit-update check` command both
subprocess this probe at runtime, but it was absent from
`FEATURE_INCLUDES["contract"]`, so a plugin install omitted it and the
release check failed. Same packaging-closure class as #570.
"""

from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = REPO / ".claude/features/rabbit-cage/install.py"
PROBE_REL = ".claude/features/contract/scripts/check-release-update.py"


def _load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_src_tree(src_root: Path, install_mod) -> None:
    def _copy_rel(rel: str) -> None:
        s = REPO / rel
        d = src_root / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    for rel in install_mod.SAME_PATH_FILES:
        _copy_rel(rel)
    for src_rel, _dst_rel in install_mod.HOOKS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.SKILLS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.AGENTS:
        _copy_rel(src_rel)
    for src_rel, _dst_rel in install_mod.COMMANDS:
        _copy_rel(src_rel)
    for feature, paths in install_mod.FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        for rel in paths:
            _copy_rel(f"{base}/{rel}")


def _run_install(install_mod, argv: list[str]) -> int:
    saved = sys.argv
    sys.argv = argv
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            return install_mod.main()
    finally:
        sys.argv = saved


def test_install_deploys_check_release_update_probe():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        dst = td_path / "dst"

        rc = _run_install(
            install, ["install.py", "--src", str(src), "--target", str(dst)]
        )
        assert rc == 0, f"install.main returned {rc}, expected 0"

        deployed_probe = dst / PROBE_REL
        assert deployed_probe.is_file(), (
            f"release-update probe not deployed: {deployed_probe} missing. "
            "FEATURE_INCLUDES['contract'] must list "
            "scripts/check-release-update.py (issue #605)."
        )
    print("PASS test_install_deploys_check_release_update_probe")


def main() -> int:
    test_install_deploys_check_release_update_probe()
    return 0


if __name__ == "__main__":
    sys.exit(main())
