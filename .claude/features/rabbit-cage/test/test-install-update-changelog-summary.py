#!/usr/bin/env python3
"""test-install-update-changelog-summary.py — e2e: after a successful
`install.py --update`, a brief changelog summary is emitted to the terminal
naming the OLD -> NEW version range and the intervening LIVE-track `vX.Y.Z`
git-tag entries (spec Inv 46, #924 re-sourced by #931).

Live releases are `vX.Y.Z` git tags cut by the release path; the repo-root
`CHANGELOG.md` is a SEPARATE frozen `release/1.x` install-branch track that the
release path does not maintain (rabbit-auto-evolve Inv 57). So the summary is
sourced from the source tree's `vX.Y.Z` git tags, NEVER from root CHANGELOG.md.

Five behaviours, exercising the REAL install.main(--update) path (the same call
install.sh / rabbit-update.py drive) into a throwaway sandbox whose source tree
is a git checkout carrying annotated `vX.Y.Z` tags:

  (a) After an update A -> B, the post-install summary names the `A -> B`
      range AND lists the tag entries strictly newer than A up to B, read from
      the source-tree git tags (NOT AI-inferred), EXCLUDING the already-
      installed tag A.
  (b) The summary content comes from the tag annotation: a sentinel string in
      a tag's annotation subject appears in the summary, proving the text is
      git-sourced rather than inferred.
  (c) A no-op refresh (old version == new version) emits NO range summary;
      at most a clean "already current" line — never a fabricated changelog.
  (d) The pure renderer `render_changelog_summary` is exported and renders
      deterministically from an in-memory `(tag, subject)` list.
  (e) A normal `vX.Y.Z` update does NOT silently degrade to a bare version
      pointer, and the summary does NOT read root `CHANGELOG.md` — a sentinel
      injected into a DEAD-track root CHANGELOG.md never appears in the output.
"""

from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
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


def _git(src_root: Path, *args: str) -> None:
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    })
    subprocess.run(["git", "-C", str(src_root), *args],
                   check=True, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# (tag, annotation-subject) pairs to lay down in the source git repo. Each
# annotated tag's subject is the human-readable release line the summary lists.
TAGS = [
    ("v9.4.9", "OLD-VERSION-SENTINEL already-installed release"),
    ("v9.4.11", "MIDDLE-VERSION-SENTINEL intervening release"),
    ("v9.4.12", "NEW-VERSION-SENTINEL changelog summary after update"),
]


def _make_tagged_src(td_path: Path, install_mod) -> Path:
    src = td_path / "src"
    src.mkdir()
    _build_src_tree(src, install_mod)
    _git(src, "init", "-q")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "base")
    for tag, subject in TAGS:
        _git(src, "tag", "-a", tag, "-m", subject)
    return src


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


def test_update_emits_range_and_intervening_tags():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = _make_tagged_src(td_path, install)
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
        # (a) lists the intervening tags (newer than old, up to new):
        # v9.4.12 (new) and v9.4.11 (middle), NOT v9.4.9 (already installed).
        assert "NEW-VERSION-SENTINEL" in stdout, (
            f"new-version tag missing from summary; got: {stdout!r}"
        )
        assert "MIDDLE-VERSION-SENTINEL" in stdout, (
            f"intervening tag missing from summary; got: {stdout!r}"
        )
        assert "OLD-VERSION-SENTINEL" not in stdout, (
            f"already-installed tag should be excluded; got: {stdout!r}"
        )
    print("PASS test_update_emits_range_and_intervening_tags")


def test_summary_text_is_read_from_git_tag():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = _make_tagged_src(td_path, install)
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
        # The tag's annotation subject appears verbatim, proving the summary
        # text is git-sourced, not inferred.
        assert "changelog summary after update" in stdout, (
            f"summary did not include the verbatim tag annotation subject; "
            f"got: {stdout!r}"
        )
    print("PASS test_summary_text_is_read_from_git_tag")


def test_noop_same_version_emits_no_range_summary():
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = _make_tagged_src(td_path, install)
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
        # tag entries are listed.
        assert "Changelog" not in stdout, (
            f"no-op refresh should not emit a changelog summary; got: {stdout!r}"
        )
        assert "MIDDLE-VERSION-SENTINEL" not in stdout, (
            f"no-op refresh should not list tag entries; got: {stdout!r}"
        )
    print("PASS test_noop_same_version_emits_no_range_summary")


def test_render_changelog_summary_is_exported_and_pure():
    install = _load_install()
    assert hasattr(install, "render_changelog_summary"), (
        "install.py must export render_changelog_summary"
    )
    # Pure render over an in-memory (tag, subject) list: select v9.4.11..v9.4.12.
    tags = [
        ("v9.4.9", "OLD-VERSION-SENTINEL already-installed release"),
        ("v9.4.11", "MIDDLE-VERSION-SENTINEL intervening release"),
        ("v9.4.12", "NEW-VERSION-SENTINEL changelog summary after update"),
    ]
    summary = install.render_changelog_summary("v9.4.9", "v9.4.12", tags)
    assert summary, "renderer returned empty for a real upgrade"
    assert "Changelog" in summary
    assert "v9.4.9 -> v9.4.12" in summary
    assert "NEW-VERSION-SENTINEL" in summary
    assert "MIDDLE-VERSION-SENTINEL" in summary
    assert "OLD-VERSION-SENTINEL" not in summary
    # Same-version: no range summary (empty or an "already current" line only).
    noop = install.render_changelog_summary("v9.4.12", "v9.4.12", tags)
    assert "v9.4.12 -> v9.4.12" not in (noop or "")
    assert "MIDDLE-VERSION-SENTINEL" not in (noop or "")
    print("PASS test_render_changelog_summary_is_exported_and_pure")


def test_summary_does_not_read_root_changelog():
    """(e) The summary sources off the live git tags, NOT the dead-track root
    CHANGELOG.md: a sentinel injected ONLY into root CHANGELOG.md never appears,
    and a normal vX.Y.Z update does NOT silently degrade (the tag lines DO
    appear)."""
    install = _load_install()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        src = _make_tagged_src(td_path, install)
        # Poison the dead-track root CHANGELOG.md with a sentinel that must
        # NEVER leak into the summary.
        (src / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [release/1.12.0]\n- DEAD-ROOT-CHANGELOG-LEAK\n"
        )
        _git(src, "add", "-A")
        _git(src, "commit", "-q", "-m", "poison root changelog")
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
        assert "DEAD-ROOT-CHANGELOG-LEAK" not in stdout, (
            f"summary leaked dead-track root CHANGELOG.md content; "
            f"got: {stdout!r}"
        )
        # Not silently degraded: the live-track tag lines DO appear.
        assert "v9.4.9 -> v9.4.12" in stdout and "NEW-VERSION-SENTINEL" in stdout, (
            f"summary silently degraded for a normal vX.Y.Z update; "
            f"got: {stdout!r}"
        )
    print("PASS test_summary_does_not_read_root_changelog")


def main() -> int:
    test_update_emits_range_and_intervening_tags()
    test_summary_text_is_read_from_git_tag()
    test_noop_same_version_emits_no_range_summary()
    test_render_changelog_summary_is_exported_and_pure()
    test_summary_does_not_read_root_changelog()
    return 0


if __name__ == "__main__":
    sys.exit(main())
