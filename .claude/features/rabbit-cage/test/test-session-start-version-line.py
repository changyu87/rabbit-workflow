#!/usr/bin/env python3
"""test-session-start-version-line.py — e2e: issue #326.

session-start-dispatcher.py emits a brief version line at the START of its
systemMessage output showing the installed rabbit version.

  - Plugin mode (detected by <install_root>/.version): the line shows the
    content of the .version file.
  - Standalone mode (no .version file): the line falls back to the
    `version` field in rabbit-cage/feature.json.

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


def test_standalone_mode_falls_back_to_feature_json_version():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_version=False)
        expected = json.loads(RABBIT_CAGE_FEATURE_JSON.read_text())["version"]
        proc = _run(install_root)
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _system_message(proc.stdout)
        assert f"rabbit v{expected}" in sysmsg, (
            f"expected feature.json version v{expected} in version line; "
            f"got {sysmsg!r}")
    print("PASS test_standalone_mode_falls_back_to_feature_json_version")


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
    test_standalone_mode_falls_back_to_feature_json_version()
    test_version_line_rendered_first()
    return 0


if __name__ == "__main__":
    sys.exit(main())
