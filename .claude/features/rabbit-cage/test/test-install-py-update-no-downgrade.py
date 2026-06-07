#!/usr/bin/env python3
"""test-install-py-update-no-downgrade.py — e2e: install.main(--update) NEVER
downgrades below the currently-installed version, and the update ACTION lands on
exactly the version the update-CHECK advertises (Inv 27 downgrade guard, #850).

The bug (#850): `install.py --update` resolved a stale ref and DOWNGRADED a
v1.14.14 install to the dead `release/1.12.0` branch, while the update-CHECK
banner advertised v9.0.26 — check and action disagreed and the action went
BACKWARDS.

These tests mock the GitHub latest lookup (via RABBIT_UPDATE_TEST_LATEST, the
same injection the check + #848's first-install path use) and the installed
version (the `<target>/.version` file), then assert:

  (1) latest NEWER than installed -> update proceeds, fetch fires on the
      resolved latest tag (the action lands on exactly the advertised version).
  (2) latest OLDER than installed -> DOWNGRADE REFUSED: no fetch, no copy,
      exit 0, "up to date" reported, .version byte-untouched.
  (3) latest EQUAL to installed -> no-op "up to date": no fetch, exit 0.
  (4) explicit --version/--ref override STILL works even when it names an older
      ref (the guard governs only the dynamic-default channel; an explicit
      operator choice is honored verbatim).
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


def _fresh_install(install, td_path: Path, installed_ref: str) -> tuple[Path, Path]:
    fixture = td_path / "fixture"
    fixture.mkdir()
    _build_src_tree(fixture, install)
    dst = td_path / "dst"
    saved_ref = os.environ.get("RABBIT_INSTALLED_REF")
    os.environ["RABBIT_INSTALLED_REF"] = installed_ref
    try:
        rc, _ = _run_install(install, ["install.py", "--src", str(fixture), "--target", str(dst)])
    finally:
        if saved_ref is None:
            os.environ.pop("RABBIT_INSTALLED_REF", None)
        else:
            os.environ["RABBIT_INSTALLED_REF"] = saved_ref
    assert rc == 0, f"fresh install must succeed; got rc={rc}"
    assert (dst / ".version").read_text().strip() == installed_ref, (
        "fresh install must pin .version to the installed ref")
    return fixture, dst


def _capture_fetch(install, fixture: Path) -> list:
    calls: list[tuple[str, str, Path]] = []

    def fake_fetch(repo: str, ref: str, dest: Path) -> Path:
        calls.append((repo, ref, dest))
        return fixture

    install.fetch_upstream = fake_fetch
    return calls


def _update(install, dst: Path, fixture: Path, *, latest: str | None, extra_argv=None) -> tuple[int, str, list]:
    """Run --update with the latest lookup injected (or forced offline-None),
    capturing fetch_upstream calls. Clears RABBIT_REF so the dynamic-default
    path runs unless extra_argv overrides it. When fetch DOES fire it returns
    the prebuilt `fixture` src tree (never `dst`, which would copy onto itself)."""
    original_fetch = install.fetch_upstream
    calls = _capture_fetch(install, fixture)
    original_resolve = install.resolve_latest_release
    saved_ref = os.environ.pop("RABBIT_REF", None)
    saved_latest = os.environ.pop("RABBIT_UPDATE_TEST_LATEST", None)
    saved_installed = os.environ.pop("RABBIT_INSTALLED_REF", None)
    # Set the re-exec loop-guard so the in-process --update stays in THIS
    # interpreter (Inv 22h) — otherwise os.execv would replace the test process
    # before our assertions run and the fetch_upstream mock would be discarded.
    saved_guard = os.environ.get(install._REEXEC_GUARD)
    os.environ[install._REEXEC_GUARD] = "1"
    if latest is None:
        install.resolve_latest_release = lambda *a, **k: None
    else:
        os.environ["RABBIT_UPDATE_TEST_LATEST"] = latest
    argv = ["install.py", "--update", "--target", str(dst)]
    if extra_argv:
        argv += extra_argv
    try:
        rc, out = _run_install(install, argv)
    finally:
        install.fetch_upstream = original_fetch
        install.resolve_latest_release = original_resolve
        os.environ.pop("RABBIT_UPDATE_TEST_LATEST", None)
        os.environ.pop("RABBIT_INSTALLED_REF", None)
        if saved_guard is None:
            os.environ.pop(install._REEXEC_GUARD, None)
        else:
            os.environ[install._REEXEC_GUARD] = saved_guard
        if saved_ref is not None:
            os.environ["RABBIT_REF"] = saved_ref
        if saved_latest is not None:
            os.environ["RABBIT_UPDATE_TEST_LATEST"] = saved_latest
        if saved_installed is not None:
            os.environ["RABBIT_INSTALLED_REF"] = saved_installed
    return rc, out, calls


def test_update_proceeds_when_latest_newer():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture, dst = _fresh_install(install, td_path, "v1.14.14")
        rc, _out, calls = _update(install, dst, fixture, latest="v9.0.26")
        assert rc == 0, f"update to a newer latest must succeed; got rc={rc}"
        assert len(calls) == 1, (
            f"fetch_upstream must fire once for an upgrade; got {len(calls)}")
        assert calls[0][1] == "v9.0.26", (
            f"update action must land on exactly the advertised latest; "
            f"fetch got ref={calls[0][1]!r}, expected 'v9.0.26'")
    print("PASS test_update_proceeds_when_latest_newer")


def test_update_refuses_downgrade():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture, dst = _fresh_install(install, td_path, "v1.14.14")
        before = (dst / ".version").read_text()
        # The dead release-branch channel (1.12.0) is OLDER than installed.
        rc, out, calls = _update(install, dst, fixture, latest="release/1.12.0")
        assert rc == 0, f"refusing a downgrade must exit 0; got rc={rc}"
        assert len(calls) == 0, (
            f"a downgrade MUST NOT fetch; fetch_upstream fired {len(calls)} time(s) "
            f"with {calls}")
        assert (dst / ".version").read_text() == before, (
            "a refused downgrade MUST leave .version byte-untouched")
        assert "up to date" in out.lower() or "no newer" in out.lower(), (
            f"a refused downgrade must report up-to-date / no-newer; got out={out!r}")
    print("PASS test_update_refuses_downgrade")


def test_update_noop_when_equal():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture, dst = _fresh_install(install, td_path, "v9.0.26")
        rc, out, calls = _update(install, dst, fixture, latest="v9.0.26")
        assert rc == 0, f"equal-version --update must exit 0; got rc={rc}"
        assert len(calls) == 0, (
            f"no newer release => no fetch; fetch_upstream fired {len(calls)} time(s)")
        assert "up to date" in out.lower() or "no newer" in out.lower(), (
            f"equal-version --update must report up-to-date; got out={out!r}")
    print("PASS test_update_noop_when_equal")


def test_explicit_version_override_bypasses_guard():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        fixture, dst = _fresh_install(install, td_path, "v9.0.26")
        # Operator explicitly asks for an OLDER ref via --version: honored verbatim,
        # the downgrade guard governs only the dynamic-default channel.
        rc, _out, calls = _update(install, dst, fixture, latest="v9.0.26",
                                  extra_argv=["--version", "v1.0.0"])
        assert rc == 0, f"explicit --version override must succeed; got rc={rc}"
        assert len(calls) == 1, (
            f"explicit --version must fetch even when older; got {len(calls)} call(s)")
        assert calls[0][1] == "v1.0.0", (
            f"explicit --version must flow verbatim to fetch; got ref={calls[0][1]!r}")
    print("PASS test_explicit_version_override_bypasses_guard")


def main() -> int:
    test_update_proceeds_when_latest_newer()
    test_update_refuses_downgrade()
    test_update_noop_when_equal()
    test_explicit_version_override_bypasses_guard()
    return 0


if __name__ == "__main__":
    sys.exit(main())
