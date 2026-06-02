#!/usr/bin/env python3
"""test-plugin-sessionstart-alert-on-active-session-override.py — Inv 16
amendment + Inv 27.

End-to-end SessionStart dispatch in plugin mode with an active
session-override marker MUST surface the red 'SCOPE GUARD OFF' banner
in the dispatcher's emitted systemMessage.

This pins the runtime visibility that bug #281 reported missing: the
operator needs the banner at session-start too (not only at Stop) so a
freshly-restored session immediately surfaces the active bypass.
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
    """Build a temp rabbit install root containing the contract feature
    (for runtime APIs), the rabbit-meta feature (for mode detection),
    and a copy of rabbit-cage's feature.json so the dispatcher
    enumerates the real runtime.SessionStart declarations.
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
    cage_dir = td / ".claude/features/rabbit-cage"
    cage_dir.mkdir(parents=True)
    shutil.copy(RABBIT_CAGE_FEATURE_JSON, cage_dir / "feature.json")
    pol = td / ".claude/features/policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("# stub\n")
    (pol / "spec-rules.md").write_text("# stub\n")
    (pol / "coding-rules.md").write_text("# stub\n")
    return td


def test_session_start_emits_scope_guard_off_banner():
    with tempfile.TemporaryDirectory() as td:
        rabbit_root = Path(td).resolve()
        _setup_temp_repo(rabbit_root)
        # Mark plugin mode AND drop the session-override marker at the
        # per-mode canonical location.
        rt = rabbit_root / ".rabbit" / ".runtime"
        rt.mkdir(parents=True)
        (rt / "mode").write_text("plugin")
        (rabbit_root / ".rabbit-scope-override").write_text("session")

        env = {**os.environ, "RABBIT_ROOT": str(rabbit_root)}
        proc = subprocess.run(
            [sys.executable, str(SESSION)],
            input="",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(rabbit_root),
        )
        assert proc.returncode == 0, (
            f"dispatcher failed rc={proc.returncode} stderr={proc.stderr!r}"
        )
        stdout = proc.stdout.strip()
        assert stdout, (
            f"dispatcher emitted no JSON. stderr={proc.stderr!r}"
        )
        try:
            emission = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"dispatcher stdout is not JSON: {stdout!r} err={e}"
            )
        # The check_marker_alert emission flows through render_emission
        # and is concatenated into hookSpecificOutput.additionalContext
        # or systemMessage depending on the dispatcher contract. We
        # accept either surface — both are operator-visible.
        haystack = json.dumps(emission)
        assert "SCOPE GUARD OFF" in haystack, (
            "SessionStart emission missing 'SCOPE GUARD OFF' banner. "
            f"emission={emission!r}"
        )
    print("PASS test_session_start_emits_scope_guard_off_banner")


def main() -> int:
    test_session_start_emits_scope_guard_off_banner()
    return 0


if __name__ == "__main__":
    sys.exit(main())
