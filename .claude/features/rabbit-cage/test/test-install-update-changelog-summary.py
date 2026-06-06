#!/usr/bin/env python3
"""test-install-update-changelog-summary.py — e2e: after a successful
`install.py --update`, a brief changelog summary is emitted to the terminal
naming the OLD -> NEW version range and the intervening CHANGELOG.md entries
(spec Inv 46, #924).

Four behaviours, all exercising the REAL install.main(--update) path (the same
call install.sh / rabbit-update.py drive) into a throwaway sandbox:

  (a) After an update A -> B, the post-install summary names the `A -> B`
      range AND lists the changelog entries between A and B, read verbatim
      from the source-tree CHANGELOG.md (NOT AI-inferred).
  (b) The summary content comes from the repo CHANGELOG.md file: a sentinel
      string injected into the source CHANGELOG.md appears in the summary,
      proving the text is sourced from the file rather than inferred.
  (c) A no-op refresh (old version == new version) emits NO range summary;
      at most a clean "already current" line — never a fabricated changelog.
  (d) The pure renderer `render_changelog_summary` is exported and parses
      sections deterministically from a CHANGELOG body string.
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


# A deterministic CHANGELOG body installed into the source tree. The summary
# must select the sections strictly newer than the OLD pin, up to NEW.
CHANGELOG_BODY = """# Changelog

All notable changes to the rabbit workflow are documented here.

## [Unreleased]
### Changed
- Closes #999 — UNRELEASED-SENTINEL placeholder bullet.

## [v9.4.12]
### Fixed
- Fixes #924 — NEW-VERSION-SENTINEL changelog summary after update.

## [v9.4.11]
### Added
- Closes #900 — MIDDLE-VERSION-SENTINEL intervening entry.

## [v9.4.9]
### Fixed
- Fixes #800 — OLD-VERSION-SENTINEL already-installed entry.
"""


def _write_changelog(root: Path, body: str) -> None:
    (root / "CHANGELOG.md").write_text(body)


def _run_install(install_mod, argv, env_overrides=None):
    saved_argv = sys.argv
    saved_env = {}
    if env_overrides:
        for k, v in env_overrides.items():
            saved_env[k] = os.environ.get(k)
            os.environ[k] = v
    buf = io.StringIO()
    sys.argv = argv
    try:
        with redirect_stdout(buf):
            rc = install_mod.main()
    finally:
        sys.argv = saved_argv
        if env_overrides:
            for k, prev in saved_env.items():
                if prev is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = prev
    return rc, buf.getvalue()


def test_update_emits_range_and_intervening_entries():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        _write_changelog(src, CHANGELOG_BODY)
        dst = td_path / "dst"

        # First install pins to v9.4.9.
        rc, _ = _run_install(
            install,
            ["install.py", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "v9.4.9"},
        )
        assert rc == 0

        # Update to v9.4.12.
        rc2, stdout = _run_install(
            install,
            ["install.py", "--update", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "v9.4.12"},
        )
        assert rc2 == 0, f"--update rc={rc2}"

        # (a) names the v9.4.9 -> v9.4.12 range in a dedicated changelog
        # summary line (distinct from the pre-existing "updating A -> B" pin
        # line). The summary banner labels the changelog explicitly.
        assert "Changelog" in stdout and "v9.4.9 -> v9.4.12" in stdout, (
            f"expected a 'Changelog' summary naming 'v9.4.9 -> v9.4.12'; "
            f"got: {stdout!r}"
        )
        # (a) lists the intervening entries (newer than old, up to new):
        # v9.4.12 (new) and v9.4.11 (middle), NOT v9.4.9 (already installed).
        assert "NEW-VERSION-SENTINEL" in stdout, (
            f"new-version entry missing from summary; got: {stdout!r}"
        )
        assert "MIDDLE-VERSION-SENTINEL" in stdout, (
            f"intervening entry missing from summary; got: {stdout!r}"
        )
        assert "OLD-VERSION-SENTINEL" not in stdout, (
            f"already-installed entry should be excluded; got: {stdout!r}"
        )
    print("PASS test_update_emits_range_and_intervening_entries")


def test_summary_text_is_read_from_changelog_file():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        # Inject a unique sentinel bullet into the NEW version's section so we
        # can prove the summary text is sourced from the file, not inferred.
        unique = "VERBATIM-FROM-FILE-PROOF-31415"
        body = CHANGELOG_BODY.replace(
            "NEW-VERSION-SENTINEL changelog summary after update.",
            f"NEW-VERSION-SENTINEL {unique}",
        )
        _write_changelog(src, body)
        dst = td_path / "dst"

        rc, _ = _run_install(
            install,
            ["install.py", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "v9.4.9"},
        )
        assert rc == 0
        rc2, stdout = _run_install(
            install,
            ["install.py", "--update", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "v9.4.12"},
        )
        assert rc2 == 0
        assert unique in stdout, (
            f"summary did not include the verbatim CHANGELOG sentinel "
            f"{unique!r}; got: {stdout!r}"
        )
    print("PASS test_summary_text_is_read_from_changelog_file")


def test_noop_same_version_emits_no_range_summary():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = td_path / "src"
        src.mkdir()
        _build_src_tree(src, install)
        _write_changelog(src, CHANGELOG_BODY)
        dst = td_path / "dst"

        rc, _ = _run_install(
            install,
            ["install.py", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "v9.4.12"},
        )
        assert rc == 0
        # Re-run --update with the SAME pin: a no-op refresh.
        rc2, stdout = _run_install(
            install,
            ["install.py", "--update", "--src", str(src), "--target", str(dst)],
            env_overrides={"RABBIT_INSTALLED_REF": "v9.4.12"},
        )
        assert rc2 == 0
        # The pre-existing Inv 22e "updating A -> B" pin line still prints, but
        # NO dedicated changelog summary is emitted for a no-op, and no
        # changelog entries are listed.
        assert "Changelog" not in stdout, (
            f"no-op refresh should not emit a changelog summary; got: {stdout!r}"
        )
        assert "MIDDLE-VERSION-SENTINEL" not in stdout, (
            f"no-op refresh should not list changelog entries; got: {stdout!r}"
        )
    print("PASS test_noop_same_version_emits_no_range_summary")


def test_render_changelog_summary_is_exported_and_pure():
    install = _load_install()
    assert hasattr(install, "render_changelog_summary"), (
        "install.py must export render_changelog_summary"
    )
    # Pure-string parse: select v9.4.11..v9.4.12 over the body.
    summary = install.render_changelog_summary("v9.4.9", "v9.4.12", CHANGELOG_BODY)
    assert summary, "renderer returned empty for a real upgrade"
    assert "Changelog" in summary
    assert "v9.4.9 -> v9.4.12" in summary
    assert "NEW-VERSION-SENTINEL" in summary
    assert "MIDDLE-VERSION-SENTINEL" in summary
    assert "OLD-VERSION-SENTINEL" not in summary
    # Same-version: no range summary (empty or an "already current" line only).
    noop = install.render_changelog_summary("v9.4.12", "v9.4.12", CHANGELOG_BODY)
    assert "v9.4.12 -> v9.4.12" not in (noop or "")
    assert "MIDDLE-VERSION-SENTINEL" not in (noop or "")
    print("PASS test_render_changelog_summary_is_exported_and_pure")


def main() -> int:
    test_update_emits_range_and_intervening_entries()
    test_summary_text_is_read_from_changelog_file()
    test_noop_same_version_emits_no_range_summary()
    test_render_changelog_summary_is_exported_and_pure()
    return 0


if __name__ == "__main__":
    sys.exit(main())
