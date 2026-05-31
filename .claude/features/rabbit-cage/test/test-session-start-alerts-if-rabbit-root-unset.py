#!/usr/bin/env python3
"""test-session-start-alerts-if-rabbit-root-unset.py — e2e: Inv 20.

When session-start-dispatcher.py runs in plugin mode (detected by the
presence of <install_root>/.version) and the RABBIT_ROOT env var is unset
or does not match the expected install root, the dispatcher emits a
banner payload (icon 🚨, color red) naming the expected install path and
recommending the tcsh + bash/zsh export commands.

Negative cases:
  - With RABBIT_ROOT correctly set to the install root, no banner.
  - In standalone mode (no .version file), the check is skipped.
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


def _build_install_root(td: Path, *, with_version: bool) -> Path:
    """Create a fake <install_root> directory containing the rabbit-cage
    dispatcher + helper at <install_root>/.claude/hooks/, the contract +
    rabbit-meta features needed for runtime imports, a minimal policy
    source for welcome_with_policy, and optionally a .version file."""
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
        (install_root / ".version").write_text("test-pin\n")

    return install_root


def _run(install_root: Path, env_overrides: dict) -> subprocess.CompletedProcess:
    dispatcher = install_root / ".claude/hooks/session-start-dispatcher.py"
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(install_root),
    )


def _extract_system_message(stdout: str) -> str:
    # Dispatcher emits at most one JSON object; tolerate empty stdout.
    stdout = stdout.strip()
    if not stdout:
        return ""
    obj = json.loads(stdout)
    return obj.get("systemMessage", "")


def test_alert_when_rabbit_root_unset_in_plugin_mode():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_version=True)
        # Pop RABBIT_ROOT entirely.
        env = dict(os.environ)
        env.pop("RABBIT_ROOT", None)
        proc = subprocess.run(
            [sys.executable, str(install_root / ".claude/hooks/session-start-dispatcher.py")],
            input="",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(install_root),
        )
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _extract_system_message(proc.stdout)
        assert str(install_root) in sysmsg, (
            f"expected install path {install_root!s} in systemMessage; "
            f"got {sysmsg!r}"
        )
        # Banner glyph indicates the alert was rendered.
        assert "🚨" in sysmsg, f"expected siren glyph in systemMessage; got {sysmsg!r}"
        # Both shell hints present.
        assert "setenv RABBIT_ROOT" in sysmsg, f"missing tcsh hint; got {sysmsg!r}"
        assert "export RABBIT_ROOT" in sysmsg, f"missing bash/zsh hint; got {sysmsg!r}"
    print("PASS test_alert_when_rabbit_root_unset_in_plugin_mode")


def test_alert_when_rabbit_root_mismatched_in_plugin_mode():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_version=True)
        proc = _run(install_root, {"RABBIT_ROOT": "/some/wrong/path"})
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _extract_system_message(proc.stdout)
        assert str(install_root) in sysmsg, (
            f"expected install path in systemMessage; got {sysmsg!r}"
        )
        assert "🚨" in sysmsg
    print("PASS test_alert_when_rabbit_root_mismatched_in_plugin_mode")


def test_no_alert_when_rabbit_root_matches_in_plugin_mode():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_version=True)
        proc = _run(install_root, {"RABBIT_ROOT": str(install_root)})
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _extract_system_message(proc.stdout)
        assert "RABBIT_ROOT" not in sysmsg or "🚨" not in sysmsg, (
            f"expected no RABBIT_ROOT siren banner when env matches; got {sysmsg!r}"
        )
    print("PASS test_no_alert_when_rabbit_root_matches_in_plugin_mode")


def test_check_skipped_in_standalone_mode():
    """No .version file -> standalone mode -> check is skipped even if
    RABBIT_ROOT is unset."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_version=False)
        env = dict(os.environ)
        env.pop("RABBIT_ROOT", None)
        proc = subprocess.run(
            [sys.executable, str(install_root / ".claude/hooks/session-start-dispatcher.py")],
            input="",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(install_root),
        )
        assert proc.returncode == 0, f"dispatcher failed: stderr={proc.stderr!r}"
        sysmsg = _extract_system_message(proc.stdout)
        # No RABBIT_ROOT banner specifically (siren + install_root path).
        assert not (str(install_root) in sysmsg and "🚨" in sysmsg), (
            f"expected NO RABBIT_ROOT alert in standalone mode; got {sysmsg!r}"
        )
    print("PASS test_check_skipped_in_standalone_mode")


def main() -> int:
    test_alert_when_rabbit_root_unset_in_plugin_mode()
    test_alert_when_rabbit_root_mismatched_in_plugin_mode()
    test_no_alert_when_rabbit_root_matches_in_plugin_mode()
    test_check_skipped_in_standalone_mode()
    return 0


if __name__ == "__main__":
    sys.exit(main())
