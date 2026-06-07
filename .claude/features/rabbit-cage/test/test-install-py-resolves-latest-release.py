#!/usr/bin/env python3
"""test-install-py-resolves-latest-release.py — e2e: install.main(--update) with no
explicit ref resolves the LATEST published release dynamically, falling back to the
hardcoded HARDCODED_STABLE_DEFAULT only when latest-resolution fails (Inv 27 (d), #848).

Mocks fetch_upstream to capture the ref argument, and drives the latest-resolution
two ways:
  (1) inject RABBIT_UPDATE_TEST_LATEST=<tag> -> the default path MUST fetch that tag
      (proves the default tracks latest dynamically, not the frozen literal).
  (2) force latest-resolution to return None (monkeypatch resolve_latest_release) ->
      the default path MUST fall back to HARDCODED_STABLE_DEFAULT and still fetch
      (proves graceful offline degradation; never installs nothing, never 'dev').
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


def _fresh_install(install, td_path: Path) -> tuple[Path, Path]:
    fixture = td_path / "fixture"
    fixture.mkdir()
    _build_src_tree(fixture, install)
    dst = td_path / "dst"
    rc, _ = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
    assert rc == 0, f"fresh install must succeed; got rc={rc}"
    return fixture, dst


def _capture_fetch(install, fixture: Path) -> list:
    calls: list[tuple[str, str, Path]] = []

    def fake_fetch(repo: str, ref: str, dest: Path) -> Path:
        calls.append((repo, ref, dest))
        return fixture

    install.fetch_upstream = fake_fetch
    return calls


def test_default_resolves_injected_latest_tag():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture, dst = _fresh_install(install, td_path)

        original_fetch = install.fetch_upstream
        calls = _capture_fetch(install, fixture)
        # Wipe any inherited override so the default (dynamic) path runs.
        saved_ref = os.environ.pop("RABBIT_REF", None)
        # main() sets RABBIT_INSTALLED_REF as a side effect; save/restore it so
        # it does not leak into the next test's fresh-install .version pin.
        saved_installed = os.environ.pop("RABBIT_INSTALLED_REF", None)
        os.environ["RABBIT_UPDATE_TEST_LATEST"] = "v9.0.26"
        try:
            rc, _ = _run_install(install, ["install.py", "--update", "--target", str(dst)])
        finally:
            install.fetch_upstream = original_fetch
            os.environ.pop("RABBIT_UPDATE_TEST_LATEST", None)
            os.environ.pop("RABBIT_INSTALLED_REF", None)
            if saved_ref is not None:
                os.environ["RABBIT_REF"] = saved_ref
            if saved_installed is not None:
                os.environ["RABBIT_INSTALLED_REF"] = saved_installed

        assert rc == 0, f"--update default path must succeed; got rc={rc}"
        assert len(calls) == 1, f"fetch_upstream must fire once; got {len(calls)}"
        captured_ref = calls[0][1]
        assert captured_ref == "v9.0.26", (
            f"default path must resolve the injected latest tag dynamically; "
            f"fetch_upstream got ref={captured_ref!r}, expected 'v9.0.26'"
        )
    print("PASS test_default_resolves_injected_latest_tag")


def test_default_falls_back_when_latest_unresolvable():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture, dst = _fresh_install(install, td_path)

        original_fetch = install.fetch_upstream
        calls = _capture_fetch(install, fixture)
        # Force latest-resolution to fail (offline simulation).
        original_resolve = install.resolve_latest_release
        install.resolve_latest_release = lambda *a, **k: None
        saved_ref = os.environ.pop("RABBIT_REF", None)
        saved_installed = os.environ.pop("RABBIT_INSTALLED_REF", None)
        os.environ.pop("RABBIT_UPDATE_TEST_LATEST", None)
        try:
            rc, _ = _run_install(install, ["install.py", "--update", "--target", str(dst)])
        finally:
            install.fetch_upstream = original_fetch
            install.resolve_latest_release = original_resolve
            os.environ.pop("RABBIT_INSTALLED_REF", None)
            if saved_ref is not None:
                os.environ["RABBIT_REF"] = saved_ref
            if saved_installed is not None:
                os.environ["RABBIT_INSTALLED_REF"] = saved_installed

        assert rc == 0, f"--update offline-fallback path must succeed; got rc={rc}"
        assert len(calls) == 1, f"fetch_upstream must fire once; got {len(calls)}"
        captured_ref = calls[0][1]
        assert captured_ref == install.HARDCODED_STABLE_DEFAULT, (
            f"when latest is unresolvable, default must fall back to "
            f"HARDCODED_STABLE_DEFAULT={install.HARDCODED_STABLE_DEFAULT!r}; "
            f"fetch_upstream got ref={captured_ref!r}"
        )
        assert captured_ref != "dev", "offline fallback must never be 'dev'"
    print("PASS test_default_falls_back_when_latest_unresolvable")


def main() -> int:
    test_default_resolves_injected_latest_tag()
    test_default_falls_back_when_latest_unresolvable()
    return 0


if __name__ == "__main__":
    sys.exit(main())
