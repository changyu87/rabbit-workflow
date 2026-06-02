#!/usr/bin/env python3
"""test-standalone-override-path-unchanged.py — Inv 27.

In STANDALONE mode (no `.rabbit/.runtime/mode == 'plugin'` file),
the session-override marker lives at `<repo_root>/.rabbit-scope-override`
exactly as before. The plugin-mode fix must NOT regress standalone
semantics:

  (a) check_marker_alert with repo_root=<tmpdir> reads
      <tmpdir>/.rabbit-scope-override and fires the red banner.
  (b) scope-guard-on.py, run with RABBIT_ROOT=<tmpdir>, deletes
      <tmpdir>/.rabbit-scope-override and does NOT touch
      <tmpdir>/.rabbit/.rabbit-scope-override (even if a stray file is
      present there).
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SCOPE_GUARD_ON = REPO / ".claude/features/rabbit-cage/scripts/scope-guard-on.py"

sys.path.insert(0, str(REPO / ".claude/features"))


def test_standalone_check_marker_alert_fires():
    from contract.lib import runtime  # type: ignore
    with tempfile.TemporaryDirectory() as td:
        repo_root = Path(td)
        (repo_root / ".rabbit-scope-override").write_text("session")
        # No .rabbit/.runtime/mode file → standalone.
        result = runtime.check_marker_alert(
            path=".rabbit-scope-override",
            content="session",
            alert={
                "text": "SCOPE GUARD OFF (session override active)",
                "icon": "🔓",
                "color": "red",
            },
            repo_root=str(repo_root),
        )
        assert result.get("type") == "print", (
            f"expected print_result on standalone marker hit, got {result!r}"
        )
        assert "SCOPE GUARD OFF" in result.get("text", "")
        assert result.get("icon") == "🔓"
        assert result.get("color") == "red"
    print("PASS test_standalone_check_marker_alert_fires")


def test_standalone_scope_guard_on_deletes_repo_root_marker():
    with tempfile.TemporaryDirectory() as td:
        repo_root = Path(td).resolve()
        marker_repo = repo_root / ".rabbit-scope-override"
        marker_repo.write_text("session")
        # Stray marker inside .rabbit/ — must NOT be touched in standalone
        # mode (no plugin-mode signature).
        stray_dir = repo_root / ".rabbit"
        stray_dir.mkdir()
        marker_stray = stray_dir / ".rabbit-scope-override"
        marker_stray.write_text("session")

        env = {**os.environ, "RABBIT_ROOT": str(repo_root)}
        proc = subprocess.run(
            [sys.executable, str(SCOPE_GUARD_ON)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(repo_root),
        )
        assert proc.returncode == 0, (
            f"scope-guard-on failed: rc={proc.returncode} stderr={proc.stderr!r}"
        )
        assert not marker_repo.exists(), (
            f"standalone scope-guard-on did not delete <repo_root>/.rabbit-scope-override "
            f"(stdout={proc.stdout!r}, stderr={proc.stderr!r})"
        )
        assert marker_stray.exists(), (
            "standalone scope-guard-on incorrectly deleted "
            "<repo_root>/.rabbit/.rabbit-scope-override (must only touch repo-root marker)"
        )
    print("PASS test_standalone_scope_guard_on_deletes_repo_root_marker")


def main() -> int:
    test_standalone_check_marker_alert_fires()
    test_standalone_scope_guard_on_deletes_repo_root_marker()
    return 0


if __name__ == "__main__":
    sys.exit(main())
