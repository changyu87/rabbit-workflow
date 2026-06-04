#!/usr/bin/env python3
"""test-session-start-version-line.py — e2e: issue #326.

session-start-dispatcher.py emits a brief version line at the START of its
systemMessage output showing the installed rabbit version.

  - Plugin mode (detected by <install_root>/.version): the line shows the
    content of the .version file (the release tag pinned at install).
  - Standalone/dev mode (no .version file): the line shows the RELEASE tag
    from `git describe --tags --abbrev=0`, or "unknown" when no tag is
    resolvable (#629). It NO LONGER reads rabbit-cage's feature.json
    `version` (the per-feature spec version is not the rabbit release).

The version line is rendered FIRST (before the welcome banner / any other
SessionStart payload).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RABBIT_CAGE = REPO / ".claude/features/rabbit-cage"
SESSION_SRC = RABBIT_CAGE / "hooks/session-start-dispatcher.py"
DISPATCHER_LIB_SRC = RABBIT_CAGE / "hooks/_dispatcher_lib.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"


def _build_install_root(td: Path, *, with_version: bool,
                        version_text: str = "v9.9.9") -> Path:
    """Create a fake <install_root> with the deployed dispatcher at
    <install_root>/.claude/hooks/, the contract + rabbit-meta features for
    runtime imports, the rabbit-cage feature.json, a minimal policy source,
    and optionally a .version file."""
    install_root = td / "rabbit_install"
    install_root.mkdir()

    hooks_dir = install_root / ".claude/hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy2(SESSION_SRC, hooks_dir / "session-start-dispatcher.py")
    shutil.copy2(DISPATCHER_LIB_SRC, hooks_dir / "_dispatcher_lib.py")

    (install_root / ".claude/features").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REPO / ".claude/features/contract",
        install_root / ".claude/features/contract",
    )
    shutil.copytree(
        REPO / ".claude/features/rabbit-meta",
        install_root / ".claude/features/rabbit-meta",
    )
    cage_dir = install_root / ".claude/features/rabbit-cage"
    cage_dir.mkdir(parents=True)
    shutil.copy2(RABBIT_CAGE_FEATURE_JSON, cage_dir / "feature.json")
    pol = install_root / ".claude/features/policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("# stub\n")
    (pol / "spec-rules.md").write_text("# stub\n")
    (pol / "coding-rules.md").write_text("# stub\n")

    if with_version:
        (install_root / ".version").write_text(version_text + "\n")

    return install_root


def _run(install_root: Path) -> subprocess.CompletedProcess:
    dispatcher = install_root / ".claude/hooks/session-start-dispatcher.py"
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(install_root),
    )


def _system_message(stdout: str) -> str:
    stdout = stdout.strip()
    assert stdout, "expected JSON on stdout"
    return json.loads(stdout).get("systemMessage", "")


def test_plugin_mode_shows_version_from_dotversion_file():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(
            td_path, with_version=True, version_text="v5.32.0")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        assert "rabbit v5.32.0" in sysmsg, (
            f"expected '.version' content in version line; got {sysmsg!r}")
    print("PASS test_plugin_mode_shows_version_from_dotversion_file")


def test_standalone_no_git_tag_shows_unknown():
    """Issue #629 Defect 1: standalone mode with NO .version and NO git tag
    (the tempdir install root is not a git repo) shows "unknown" — NOT the
    rabbit-cage feature.json version."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_version=False)
        cage_version = json.loads(
            RABBIT_CAGE_FEATURE_JSON.read_text())["version"]
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        assert "rabbit vunknown" in sysmsg or "rabbit unknown" in sysmsg, (
            f"expected 'unknown' when no .version and no git tag; "
            f"got {sysmsg!r}")
        assert f"rabbit v{cage_version}" not in sysmsg, (
            f"version box must NOT show rabbit-cage feature.json version "
            f"v{cage_version}; got {sysmsg!r}")
    print("PASS test_standalone_no_git_tag_shows_unknown")


def _git(install_root: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(
        ["git", "-C", str(install_root), *args],
        check=True, capture_output=True, text=True, env=env)


def test_standalone_with_git_tag_shows_tag():
    """Issue #629 Defect 1: standalone mode with NO .version but a git tag
    shows the RELEASE TAG (from `git describe --tags --abbrev=0`), not the
    rabbit-cage feature.json version."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_version=False)
        cage_version = json.loads(
            RABBIT_CAGE_FEATURE_JSON.read_text())["version"]
        _git(install_root, "init", "-q")
        _git(install_root, "add", "-A")
        _git(install_root, "commit", "-q", "-m", "init")
        _git(install_root, "tag", "v7.7.7")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        assert "rabbit v7.7.7" in sysmsg, (
            f"expected git release tag v7.7.7 in version box; got {sysmsg!r}")
        assert f"rabbit v{cage_version}" not in sysmsg, (
            f"version box must NOT show feature.json version v{cage_version}; "
            f"got {sysmsg!r}")
    print("PASS test_standalone_with_git_tag_shows_tag")


def test_version_line_rendered_first():
    """The version line must appear before the welcome banner."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(
            td_path, with_version=True, version_text="v1.2.3")
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        ver_idx = sysmsg.find("rabbit v1.2.3")
        welcome_idx = sysmsg.find("Welcome")
        assert ver_idx != -1, f"version line missing; got {sysmsg!r}"
        assert welcome_idx != -1, f"welcome banner missing; got {sysmsg!r}"
        assert ver_idx < welcome_idx, (
            f"version line must precede welcome banner; got {sysmsg!r}")
    print("PASS test_version_line_rendered_first")


def main() -> int:
    test_plugin_mode_shows_version_from_dotversion_file()
    test_standalone_no_git_tag_shows_unknown()
    test_standalone_with_git_tag_shows_tag()
    test_version_line_rendered_first()
    return 0


if __name__ == "__main__":
    sys.exit(main())
