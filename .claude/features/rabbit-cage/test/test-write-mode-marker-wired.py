#!/usr/bin/env python3
"""test-write-mode-marker-wired.py — e2e: rabbit-cage SessionStart dispatcher
invokes contract.lib.runtime.write_mode_marker, which writes the detected
operating mode to <repo_root>/.rabbit/.runtime/mode.

Vendored-mode signature: cwd is `.rabbit/` AND its parent has a sibling entry.
This test arranges that signature inside a temp repo and asserts the
SessionStart dispatcher (driven by rabbit-cage's own feature.json) produces
the `.rabbit/.runtime/mode` file whose content DUAL-ACCEPTS the vendored-mode
value — "vendored" (canonical) or the legacy "plugin" — since
write_mode_marker writes detect_mode's value verbatim and rabbit-meta is
renaming it (Inv 50).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SESSION = REPO / ".claude/features/rabbit-cage/hooks/session-start-dispatcher.py"
RABBIT_CAGE_FEATURE_JSON = REPO / ".claude/features/rabbit-cage/feature.json"


def _setup_temp_repo(td: Path) -> Path:
    """Build a temp repo containing the real contract feature, the real
    rabbit-meta feature (for the lazy detect_mode import), and a copy of
    rabbit-cage's feature.json so the SessionStart dispatcher enumerates
    the actual rabbit-cage runtime declarations.
    """
    (td / ".claude/features").mkdir(parents=True)
    shutil.copytree(
        REPO / ".claude/features/contract",
        td / ".claude/features/contract",
    )
    shutil.copytree(
        REPO / ".claude/features/rabbit-meta",
        td / ".claude/features/rabbit-meta",
    )
    # Stage rabbit-cage's feature.json (no other files needed; the dispatcher
    # reads feature.json runtime.SessionStart and invokes contract.lib.runtime).
    cage_dir = td / ".claude/features/rabbit-cage"
    cage_dir.mkdir(parents=True)
    shutil.copy(RABBIT_CAGE_FEATURE_JSON, cage_dir / "feature.json")
    # Minimal policy source so welcome_with_policy succeeds.
    pol = td / ".claude/features/policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("# stub\n")
    (pol / "spec-rules.md").write_text("# stub\n")
    (pol / "coding-rules.md").write_text("# stub\n")
    return td


def _run_session_start(repo_root: Path, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "RABBIT_ROOT": str(repo_root)}
    return subprocess.run(
        [sys.executable, str(SESSION)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
    )


def test_session_start_writes_plugin_mode_marker():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        root = _setup_temp_repo(td_path)
        # Build the plugin signature: a sibling entry next to a `.rabbit/` dir.
        host = td_path / "host"
        host.mkdir()
        (host / "sibling.txt").write_text("present so parent has non-.rabbit entry\n")
        rabbit_dir = host / ".rabbit"
        rabbit_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(rabbit_dir)
            proc = _run_session_start(root, rabbit_dir)
        finally:
            os.chdir(original_cwd)

        assert proc.returncode == 0, f"dispatcher failed: {proc.stderr}"

        marker = root / ".rabbit/.runtime/mode"
        assert marker.is_file(), (
            f"expected mode marker at {marker} after SessionStart dispatch; "
            f"stderr={proc.stderr!r} stdout={proc.stdout!r}"
        )
        content = marker.read_text()
        # Dual-accept (Inv 50): write_mode_marker writes detect_mode's value
        # VERBATIM, and rabbit-meta is renaming the vendored-mode value from
        # "plugin" to "vendored". Accept EITHER so this stays green across the
        # detect_mode flip.
        assert content in ("vendored", "plugin"), (
            f"expected mode marker content 'vendored' or 'plugin', "
            f"got {content!r}"
        )
    print("PASS test_session_start_writes_plugin_mode_marker")


def test_feature_json_declares_write_mode_marker_entry():
    """Structural assertion: rabbit-cage feature.json runtime.SessionStart
    lists write_mode_marker AFTER welcome_with_policy."""
    data = json.loads(RABBIT_CAGE_FEATURE_JSON.read_text())
    entries = data["runtime"]["SessionStart"]
    apis = [e["api"] for e in entries]
    assert "write_mode_marker" in apis, (
        f"write_mode_marker not declared in SessionStart; got {apis}"
    )
    assert "welcome_with_policy" in apis, "welcome_with_policy missing"
    assert apis.index("write_mode_marker") > apis.index("welcome_with_policy"), (
        f"write_mode_marker must come AFTER welcome_with_policy; got {apis}"
    )
    # Args should be empty: write_mode_marker takes only repo_root (injected).
    wmm = next(e for e in entries if e["api"] == "write_mode_marker")
    assert wmm.get("args", {}) == {}, (
        f"write_mode_marker entry should have args={{}}, got {wmm.get('args')}"
    )
    print("PASS test_feature_json_declares_write_mode_marker_entry")


def main() -> int:
    test_feature_json_declares_write_mode_marker_entry()
    test_session_start_writes_plugin_mode_marker()
    return 0


if __name__ == "__main__":
    sys.exit(main())
