#!/usr/bin/env python3
"""test-install-py-version-flag-overrides-default.py — e2e: install.main(--update --version <ref>)
resolves ref from CLI flag, overriding both RABBIT_REF env var and the hardcoded default (Inv 29 (a)).

Mocks fetch_upstream to capture the ref argument; asserts the captured ref
matches the value passed via --version. Validates bug #287 fix: csh/tcsh users
have a shell-agnostic way to pin the update target without inline env-var syntax.
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


def test_version_flag_overrides_default():
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
        # Force RABBIT_REF env var so we can prove --version takes precedence.
        saved_env = os.environ.get("RABBIT_REF")
        os.environ["RABBIT_REF"] = "release/0.9"
        try:
            rc2, _ = _run_install(
                install,
                ["install.py", "--update", "--target", str(dst), "--version", "release/1.0"],
            )
        finally:
            install.fetch_upstream = original
            if saved_env is None:
                os.environ.pop("RABBIT_REF", None)
            else:
                os.environ["RABBIT_REF"] = saved_env

        assert rc2 == 0, f"--update --version must succeed; got rc={rc2}"
        assert len(calls) == 1, f"fetch_upstream must fire once; got {len(calls)}"
        captured_ref = calls[0][1]
        assert captured_ref == "release/1.0", (
            f"--version release/1.0 must win over RABBIT_REF env and hardcoded default; "
            f"fetch_upstream got ref={captured_ref!r}"
        )
    print("PASS test_version_flag_overrides_default")


def main() -> int:
    test_version_flag_overrides_default()
    return 0


if __name__ == "__main__":
    sys.exit(main())
