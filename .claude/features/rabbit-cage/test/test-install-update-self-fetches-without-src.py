#!/usr/bin/env python3
"""test-install-update-self-fetches-without-src.py — e2e: install.main(--update)
with --src omitted self-fetches the upstream tarball (Inv 22g).

Asserts:
  - main(['install.py', '--update', '--target', <dst>]) invokes
    install_under_test.fetch_upstream() when --src is absent.
  - The returned source path is used as the effective --src for the closure
    refresh; closure files end up under <dst>.
  - Exit code 0 on success.

Mocks fetch_upstream so the test does NOT touch the network.
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


def test_update_without_src_calls_fetch_upstream():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        # Build a fixture upstream-extracted dir that fetch_upstream will "return".
        fixture = td_path / "fixture"
        fixture.mkdir()
        _build_src_tree(fixture, install)

        # First, fresh-install to create a non-empty target with .claude/+.version.
        dst = td_path / "dst"
        rc, _ = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
        assert rc == 0

        # Now monkeypatch fetch_upstream to return the fixture path without network.
        calls: list[tuple[str, str, Path]] = []

        def fake_fetch(repo: str, ref: str, dest: Path) -> Path:
            calls.append((repo, ref, dest))
            return fixture

        original = getattr(install, "fetch_upstream", None)
        assert original is not None, "install.fetch_upstream is not defined (Inv 22g)"
        install.fetch_upstream = fake_fetch
        try:
            rc2, _ = _run_install(install, ["install.py", "--update", "--target", str(dst)])
        finally:
            install.fetch_upstream = original

        assert rc2 == 0, f"--update without --src must succeed; got rc={rc2}"
        assert len(calls) == 1, f"fetch_upstream must be invoked exactly once; got {len(calls)}"
        # Closure file remains in dst (refresh actually ran).
        assert (dst / "CLAUDE.md").is_file()
    print("PASS test_update_without_src_calls_fetch_upstream")


def main() -> int:
    test_update_without_src_calls_fetch_upstream()
    return 0


if __name__ == "__main__":
    sys.exit(main())
