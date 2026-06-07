#!/usr/bin/env python3
"""test-plugin-sessionstart-alert-at-canonical-override-path.py — issue #917.

Bug: in PLUGIN mode the session scope-override marker's canonical location is
`<rabbit_root>/.rabbit/.rabbit-scope-override` (Inv 25, written/read/deleted by
scope-guard.py via `_override_marker_path()` and the `.rabbit/.rabbit-scope-override`
plugin carve-out). But rabbit-cage's `runtime.SessionStart` only declared a
`check_marker_alert` for the relative path `.rabbit-scope-override`, which
`contract.lib.runtime` resolves against `repo_root` to the STANDALONE location
`<rabbit_root>/.rabbit-scope-override`. So when a plugin-mode session has an
ACTIVE override at its real canonical location, NO `[rabbit]` SCOPE GUARD OFF
notice fired at SessionStart — the user was never told the scope guard was
bypassed, asymmetric with the always-present bypass-permissions notice.

The fix adds a SECOND `check_marker_alert` SessionStart (and Stop) entry whose
path is the plugin-mode canonical `.rabbit/.rabbit-scope-override`, so the
banner fires in BOTH modes. The two entries never double-fire: the marker only
ever lives at ONE canonical location per mode, and check_marker_alert no-ops on
an absent marker.

This test is end-to-end: it drives the REAL session-start-dispatcher subprocess
against a faithful plugin install root.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the session scope-override mechanism is retired or
the per-mode marker location collapses to a single path across both modes.
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

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  PASS {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def _setup_temp_repo(td: Path) -> Path:
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


def _run(rabbit_root: Path) -> str:
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
    assert stdout, f"dispatcher emitted no JSON. stderr={proc.stderr!r}"
    return json.loads(stdout).get("systemMessage", "")


def main() -> int:
    # A. Plugin mode, override at the CANONICAL plugin path -> banner fires.
    with tempfile.TemporaryDirectory() as td:
        rr = Path(td).resolve()
        _setup_temp_repo(rr)
        rt = rr / ".rabbit" / ".runtime"
        rt.mkdir(parents=True)
        (rt / "mode").write_text("plugin")
        (rr / ".rabbit" / ".rabbit-scope-override").write_text("session")
        msg = _run(rr)
        if "SCOPE GUARD OFF" in msg:
            ok("plugin + .rabbit/.rabbit-scope-override=session -> SCOPE GUARD OFF emitted")
        else:
            ko("plugin canonical override active but SCOPE GUARD OFF NOT emitted")
        # The notice is [rabbit]-branded (rendered via rabbit_subline) and red.
        if "[" in msg and "rabbit" in msg:
            ok("notice is [rabbit]-branded")
        else:
            ko("notice missing [rabbit] branding")

    # B. Plugin mode, NO override marker -> banner silent.
    with tempfile.TemporaryDirectory() as td:
        rr = Path(td).resolve()
        _setup_temp_repo(rr)
        rt = rr / ".rabbit" / ".runtime"
        rt.mkdir(parents=True)
        (rt / "mode").write_text("plugin")
        msg = _run(rr)
        if "SCOPE GUARD OFF" not in msg:
            ok("plugin + no override -> SCOPE GUARD OFF silent")
        else:
            ko("SCOPE GUARD OFF fired with no override present")

    # C. A per-feature .rabbit-scope-active-<feature> marker alone -> silent.
    #    Per-feature markers are the normal bounded-scope mechanism, NOT a
    #    session override; they must not trip the scope-guard-off notice.
    with tempfile.TemporaryDirectory() as td:
        rr = Path(td).resolve()
        _setup_temp_repo(rr)
        rt = rr / ".rabbit" / ".runtime"
        rt.mkdir(parents=True)
        (rt / "mode").write_text("plugin")
        (rr / ".rabbit-scope-active-rabbit-cage").write_text("rabbit-cage")
        (rt / "scope-active-rabbit-cage").write_text("rabbit-cage")
        msg = _run(rr)
        if "SCOPE GUARD OFF" not in msg:
            ok("per-feature scope-active marker alone -> SCOPE GUARD OFF silent")
        else:
            ko("per-feature marker tripped the SCOPE GUARD OFF notice")

    # D. Standalone regression: override at the standalone path still fires.
    with tempfile.TemporaryDirectory() as td:
        rr = Path(td).resolve()
        _setup_temp_repo(rr)
        (rr / ".rabbit-scope-override").write_text("session")
        msg = _run(rr)
        if "SCOPE GUARD OFF" in msg:
            ok("standalone + .rabbit-scope-override=session -> SCOPE GUARD OFF emitted")
        else:
            ko("standalone override active but SCOPE GUARD OFF NOT emitted (regression)")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
