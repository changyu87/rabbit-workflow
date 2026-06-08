#!/usr/bin/env python3
"""test-plugin-stop-alert-fires-when-session-override-active.py — Inv 25.

In plugin/vendored mode the session-override marker `.rabbit-scope-override`
content `'session'` lives INSIDE the install dir at
`<git-toplevel>/.rabbit/.rabbit-scope-override` (the install directory whose
`.rabbit/.runtime/mode == 'plugin'`).

contract.lib.runtime.check_marker_alert (#1113) resolves a repo-root marker
against the GIT TOPLEVEL (markers root) — `dirname(repo_root)` when vendored —
so a repo-root-written marker like rabbit-feature's `.rabbit-tdd-autonomous`
(written at the toplevel) fires. A marker that lives INSIDE `.rabbit` must
therefore be declared with the explicit `.rabbit/`-prefixed path so it
resolves back into the install dir: joining the toplevel with
`".rabbit/.rabbit-scope-override"` yields `<repo_root>/.rabbit-scope-override`.
That is exactly the rabbit-cage SessionStart/Stop PLUGIN entry (Inv 25 entry
5). In plugin mode the dispatcher passes the rabbit install root as
`repo_root`, so the `.rabbit/`-prefixed entry finds the marker at
`<rabbit_root>/.rabbit-scope-override` and a red SCOPE GUARD OFF banner fires.

This test isolates the runtime API behaviour. The sibling test
`test-plugin-sessionstart-alert-on-active-session-override.py` covers
the end-to-end SessionStart dispatch chain.
"""

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CONTRACT_LIB = REPO / ".claude/features/contract"

# Allow `import contract.lib.runtime as runtime` from the live tree.
sys.path.insert(0, str(REPO / ".claude/features"))


def test_plugin_check_marker_alert_fires_on_session_override():
    from contract.lib import runtime  # type: ignore

    with tempfile.TemporaryDirectory() as td:
        rabbit_root = Path(td) / ".rabbit"
        runtime_dir = rabbit_root / ".runtime"
        runtime_dir.mkdir(parents=True)
        # A sibling entry so detect_mode reads the host as vendored.
        (Path(td) / "src").mkdir()
        # Plugin-mode signature.
        (runtime_dir / "mode").write_text("plugin")
        # Session override marker at the per-mode canonical location
        # (INSIDE .rabbit in plugin mode).
        (rabbit_root / ".rabbit-scope-override").write_text("session")

        # The PLUGIN entry declares the `.rabbit/`-prefixed path so it resolves
        # back into the install dir under markers-root resolution (#1113).
        result = runtime.check_marker_alert(
            path=".rabbit/.rabbit-scope-override",
            content="session",
            alert={
                "text": "SCOPE GUARD OFF (session override active)",
                "icon": "🔓",
                "color": "red",
            },
            repo_root=str(rabbit_root),
        )

        # check_marker_alert returns a print_result dict on positive match.
        assert result.get("type") == "print", (
            f"expected print_result, got {result!r}"
        )
        assert "SCOPE GUARD OFF" in result.get("text", ""), (
            f"alert text missing 'SCOPE GUARD OFF': {result!r}"
        )
        assert result.get("icon") == "🔓", (
            f"alert icon mismatch: {result!r}"
        )
        assert result.get("color") == "red", (
            f"alert color mismatch: {result!r}"
        )
    print("PASS test_plugin_check_marker_alert_fires_on_session_override")


def test_plugin_check_marker_alert_silent_when_marker_absent():
    """Sanity check: no marker → ok_result (no banner)."""
    from contract.lib import runtime  # type: ignore

    with tempfile.TemporaryDirectory() as td:
        rabbit_root = Path(td) / ".rabbit"
        rabbit_root.mkdir()
        result = runtime.check_marker_alert(
            path=".rabbit-scope-override",
            content="session",
            alert={
                "text": "SCOPE GUARD OFF (session override active)",
                "icon": "🔓",
                "color": "red",
            },
            repo_root=str(rabbit_root),
        )
        assert result.get("type") == "ok", (
            f"expected ok_result when marker absent, got {result!r}"
        )
    print("PASS test_plugin_check_marker_alert_silent_when_marker_absent")


def main() -> int:
    test_plugin_check_marker_alert_fires_on_session_override()
    test_plugin_check_marker_alert_silent_when_marker_absent()
    return 0


if __name__ == "__main__":
    sys.exit(main())
