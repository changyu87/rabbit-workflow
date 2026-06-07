#!/usr/bin/env python3
"""test-install-update-explicit-src-skips-fetch.py — e2e: explicit --src
short-circuits self-fetch (Inv 22g). When --src is supplied, fetch_upstream
MUST NOT be invoked even under --update.
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


def test_explicit_src_skips_fetch_upstream():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture = td_path / "fixture"
        fixture.mkdir()
        _build_src_tree(fixture, install)
        dst = td_path / "dst"

        rc, _ = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
        assert rc == 0

        # Counter-based mock: incremented if fetch_upstream is invoked.
        calls = {"n": 0}

        def fake_fetch(repo: str, ref: str, dest: Path) -> Path:
            calls["n"] += 1
            return fixture

        original = getattr(install, "fetch_upstream", None)
        assert original is not None, "install.fetch_upstream is not defined (Inv 22g)"
        install.fetch_upstream = fake_fetch
        try:
            rc2, _ = _run_install(
                install,
                ["install.py", "--update", "--src", str(fixture), "--target", str(dst)],
            )
        finally:
            install.fetch_upstream = original

        assert rc2 == 0, f"--update --src must succeed; got rc={rc2}"
        assert calls["n"] == 0, (
            f"fetch_upstream must NOT be invoked when --src is supplied; got {calls['n']} calls"
        )
    print("PASS test_explicit_src_skips_fetch_upstream")


def main() -> int:
    test_explicit_src_skips_fetch_upstream()
    return 0


if __name__ == "__main__":
    sys.exit(main())
