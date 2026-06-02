#!/usr/bin/env python3
"""test-install-py-channel-dev-opt-in.py — e2e: install.main(--update --channel dev)
resolves ref to literal 'dev' (Inv 29 (b)).

Mocks fetch_upstream to capture the ref argument; asserts the captured ref is
exactly 'dev' when --channel dev is supplied. Validates the explicit opt-in
path for developers wanting bleeding-edge — the user MUST name 'dev' to land
on it.
"""

from __future__ import annotations

import importlib.util
import io
import os
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


def test_channel_dev_opt_in():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture = td_path / "fixture"
        fixture.mkdir()
        _build_src_tree(fixture, install)

        dst = td_path / "dst"
        rc, _ = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
        assert rc == 0

        calls: list[tuple[str, str, Path]] = []

        def fake_fetch(repo: str, ref: str, dest: Path) -> Path:
            calls.append((repo, ref, dest))
            return fixture

        original = install.fetch_upstream
        install.fetch_upstream = fake_fetch
        # Clear RABBIT_REF to prove --channel dev resolves to 'dev' on its own.
        saved_env = os.environ.pop("RABBIT_REF", None)
        try:
            rc2, _ = _run_install(
                install,
                ["install.py", "--update", "--target", str(dst), "--channel", "dev"],
            )
        finally:
            install.fetch_upstream = original
            if saved_env is not None:
                os.environ["RABBIT_REF"] = saved_env

        assert rc2 == 0, f"--update --channel dev must succeed; got rc={rc2}"
        assert len(calls) == 1, f"fetch_upstream must fire once; got {len(calls)}"
        captured_ref = calls[0][1]
        assert captured_ref == "dev", (
            f"--channel dev must resolve to literal 'dev'; fetch_upstream got ref={captured_ref!r}"
        )
    print("PASS test_channel_dev_opt_in")


def main() -> int:
    test_channel_dev_opt_in()
    return 0


if __name__ == "__main__":
    sys.exit(main())
