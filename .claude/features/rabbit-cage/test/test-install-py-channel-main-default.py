#!/usr/bin/env python3
"""test-install-py-channel-main-default.py — e2e: main-centric channel model.

Inv 27 (b) main-centric amendment: `install.py --update --channel main` resolves
the fetch ref to the literal 'main'. `main` is the default-development channel
that the moving-tip tracks; `dev` remains an explicit opt-in channel during the
coexistence window (asserted by test-install-py-channel-dev-opt-in.py). This
test mocks fetch_upstream to capture the ref argument and asserts the captured
ref is exactly 'main' when --channel main is supplied — proving main is a
first-class accepted channel that resolves to ref 'main' (NOT to the dynamic
latest-release default, NOT to 'dev').
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


def test_channel_main_resolves_to_main():
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
        # Clear RABBIT_REF so --channel main resolves to 'main' on its own.
        saved_env = os.environ.pop("RABBIT_REF", None)
        try:
            rc2, _ = _run_install(
                install,
                ["install.py", "--update", "--target", str(dst), "--channel", "main"],
            )
        finally:
            install.fetch_upstream = original
            if saved_env is not None:
                os.environ["RABBIT_REF"] = saved_env

        assert rc2 == 0, f"--update --channel main must succeed; got rc={rc2}"
        assert len(calls) == 1, f"fetch_upstream must fire once; got {len(calls)}"
        captured_ref = calls[0][1]
        assert captured_ref == "main", (
            f"--channel main must resolve to literal 'main'; "
            f"fetch_upstream got ref={captured_ref!r}"
        )
    print("PASS test_channel_main_resolves_to_main")


def test_main_is_accepted_channel_choice():
    """The argparse --channel flag MUST accept 'main' (main-centric default
    channel) alongside the opt-in 'dev' and the dynamic-latest 'stable'."""
    src = INSTALL_PY.read_text()
    # The channel choices list must include 'main' so the main-centric channel
    # is a first-class, parser-accepted value (not rejected by argparse).
    assert '"main"' in src, "install.py --channel choices must include 'main'"
    # Coexistence: 'dev' MUST still be an accepted opt-in channel.
    assert '"dev"' in src, "install.py --channel choices must still include 'dev'"
    print("PASS test_main_is_accepted_channel_choice")


def main() -> int:
    test_channel_main_resolves_to_main()
    test_main_is_accepted_channel_choice()
    return 0


if __name__ == "__main__":
    sys.exit(main())
