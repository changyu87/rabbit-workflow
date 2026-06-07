#!/usr/bin/env python3
"""test-install-update-infers-target-from-script-location.py — e2e: when
--update is set and --target is omitted, install.py infers --target as the
directory containing the running install.py (Inv 22g).
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


def _run_install(install_mod, argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    saved = sys.argv
    sys.argv = argv
    try:
        with redirect_stdout(buf):
            rc = install_mod.main()
    finally:
        sys.argv = saved
    return rc, buf.getvalue()


def test_update_without_target_infers_from_script_location():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture = td_path / "fixture"
        fixture.mkdir()
        _build_src_tree(fixture, install)

        # Set up a fake "installed" rabbit dir that contains .claude/ and .version.
        dst = td_path / "fake-install"
        rc, _ = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
        assert rc == 0

        # Copy install.py into dst so __file__-resolution lands inside dst.
        shutil.copy2(INSTALL_PY, dst / "install.py")

        # Re-import the copied install.py so __file__ points inside dst.
        spec = importlib.util.spec_from_file_location("install_in_dst", dst / "install.py")
        mod_in_dst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod_in_dst)

        # Invoke main with --update --src <fixture> and NO --target.
        # Expect target to be inferred as dst.
        rc2, _ = _run_install(
            mod_in_dst,
            ["install.py", "--update", "--src", str(fixture)],
        )
        assert rc2 == 0, f"--update without --target must succeed when inferred dir is valid; got rc={rc2}"
        # Refresh actually ran into dst.
        assert (dst / "CLAUDE.md").is_file()
        assert (dst / ".version").is_file()
    print("PASS test_update_without_target_infers_from_script_location")


def main() -> int:
    test_update_without_target_infers_from_script_location()
    return 0


if __name__ == "__main__":
    sys.exit(main())
