#!/usr/bin/env python3
"""test-advisory-restart-surfaced.py — e2e: issue #545 (rabbit-cage part B).

The Stop and SessionStart dispatchers surface rabbit-auto-evolve's ADVISORY
restart signal by INVOKING `scripts/advise-restart.py` (a contract INVOKE, NOT
a cross-feature edit) and consuming its JSON verdict:

  - `advise-restart.py status` → {"advised": true, "reason": "<reason>"} when
    the `.rabbit-auto-evolve-restart-advised` marker is present; otherwise
    {"advised": false}.
  - `advise-restart.py clear` → removes the marker (idempotent).

While the advisory marker is present:
  - Stop emits ONE concise advisory line per tick-end
    (`restart ADVISED (not required): <reason> — loop continues meanwhile`,
    icon 🔄) and does NOT clear the marker (persists across tick-ends).
  - SessionStart surfaces the SAME advisory line in its banner AND clears the
    marker (the advised restart has now occurred).

The advisory wording is deliberately distinct from the hard #503 auto-resume
banner (`Auto-resuming rabbit-auto-evolve loop`) — it reads as OPTIONAL and
never implies a pause.

Graceful degradation (mirror #503): if advise-restart.py is absent, exits
non-zero, times out, or emits unparseable JSON → no advisory line, no crash,
no clear, dispatchers continue normally (exit 0, welcome intact).

This is an end-to-end test: it builds a fake install root with the deployed
dispatchers and the real advise-restart.py, sets the advisory marker on disk,
runs the dispatchers as subprocesses, and asserts on the emitted JSON.
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
STOP_SRC = RABBIT_CAGE / "hooks/stop-dispatcher.py"
SESSION_SRC = RABBIT_CAGE / "hooks/session-start-dispatcher.py"
DISPATCHER_LIB_SRC = RABBIT_CAGE / "hooks/_dispatcher_lib.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"
ADVISE_RESTART_SRC = (
    REPO / ".claude/features/rabbit-auto-evolve/scripts/advise-restart.py"
)

ADVISORY_MARKER = ".rabbit-auto-evolve-restart-advised"
ADVISORY_REASON = "activates skill-creator + code-review"
# The advisory line must contain this distinctive optional-restart phrasing.
ADVISORY_FRAGMENT = "restart ADVISED (not required)"
ADVISORY_TAIL = "loop continues meanwhile"
# The hard #503 banner — the advisory must be DISTINCT from this.
HARD_RESUME_FRAGMENT = "Auto-resuming rabbit-auto-evolve"


def _build_install_root(td: Path, *, with_advise_script: bool = True) -> Path:
    """Fake <install_root> with the deployed Stop + SessionStart dispatchers,
    the contract + rabbit-meta features for runtime imports, the rabbit-cage
    feature.json, a stub policy source, and (optionally) the real
    advise-restart.py at its canonical path."""
    install_root = td / "rabbit_install"
    install_root.mkdir()

    hooks_dir = install_root / ".claude/hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy2(STOP_SRC, hooks_dir / "stop-dispatcher.py")
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

    if with_advise_script:
        ae_scripts = install_root / ".claude/features/rabbit-auto-evolve/scripts"
        ae_scripts.mkdir(parents=True)
        shutil.copy2(ADVISE_RESTART_SRC, ae_scripts / "advise-restart.py")

    return install_root


def _run(dispatcher: Path, install_root: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(install_root),
    )


def _stop(install_root: Path) -> subprocess.CompletedProcess:
    return _run(install_root / ".claude/hooks/stop-dispatcher.py", install_root)


def _session(install_root: Path) -> subprocess.CompletedProcess:
    return _run(
        install_root / ".claude/hooks/session-start-dispatcher.py", install_root
    )


def _emission(proc: subprocess.CompletedProcess) -> dict:
    out = proc.stdout.strip()
    if not out:
        return {}
    return json.loads(out)


def _marker_present(install_root: Path) -> bool:
    return (install_root / ADVISORY_MARKER).exists()


def test_marker_present_stop_emits_advisory_line():
    """Advisory marker present → Stop emits the advisory line, distinct from
    the hard resume banner, and does NOT clear the marker."""
    with tempfile.TemporaryDirectory() as td:
        install_root = _build_install_root(Path(td).resolve())
        (install_root / ADVISORY_MARKER).write_text(ADVISORY_REASON)
        proc = _stop(install_root)
        assert proc.returncode == 0, f"stop failed: stderr={proc.stderr!r}"
        sysmsg = _emission(proc).get("systemMessage", "")
        assert ADVISORY_FRAGMENT in sysmsg, (
            f"Stop advisory line missing; got {sysmsg!r}")
        assert ADVISORY_REASON in sysmsg, (
            f"Stop advisory reason missing; got {sysmsg!r}")
        assert ADVISORY_TAIL in sysmsg, (
            f"Stop advisory tail missing; got {sysmsg!r}")
        assert HARD_RESUME_FRAGMENT not in sysmsg, (
            f"advisory must be distinct from hard resume; got {sysmsg!r}")
        # Stop MUST NOT clear the marker (persists across tick-ends).
        assert _marker_present(install_root), (
            "Stop must not clear the advisory marker")
    print("PASS test_marker_present_stop_emits_advisory_line")


def test_marker_present_session_emits_advisory_and_clears():
    """Advisory marker present → SessionStart surfaces the advisory line in its
    banner AND clears the marker (the advised restart has occurred)."""
    with tempfile.TemporaryDirectory() as td:
        install_root = _build_install_root(Path(td).resolve())
        (install_root / ADVISORY_MARKER).write_text(ADVISORY_REASON)
        proc = _session(install_root)
        assert proc.returncode == 0, f"session failed: stderr={proc.stderr!r}"
        sysmsg = _emission(proc).get("systemMessage", "")
        assert ADVISORY_FRAGMENT in sysmsg, (
            f"SessionStart advisory line missing; got {sysmsg!r}")
        assert ADVISORY_REASON in sysmsg, (
            f"SessionStart advisory reason missing; got {sysmsg!r}")
        assert HARD_RESUME_FRAGMENT not in sysmsg, (
            f"advisory must be distinct from hard resume; got {sysmsg!r}")
        # Welcome must still be present.
        assert "philosophy.md" in sysmsg, (
            f"existing welcome must survive; got {sysmsg!r}")
        # SessionStart MUST clear the marker after surfacing it.
        assert not _marker_present(install_root), (
            "SessionStart must clear the advisory marker after surfacing")
    print("PASS test_marker_present_session_emits_advisory_and_clears")


def test_marker_absent_no_advisory_line():
    """No advisory marker → neither dispatcher emits an advisory line; the
    SessionStart welcome is intact."""
    with tempfile.TemporaryDirectory() as td:
        install_root = _build_install_root(Path(td).resolve())
        stop = _stop(install_root)
        assert stop.returncode == 0, stop.stderr
        assert ADVISORY_FRAGMENT not in _emission(stop).get("systemMessage", "")
        session = _session(install_root)
        assert session.returncode == 0, session.stderr
        smsg = _emission(session).get("systemMessage", "")
        assert ADVISORY_FRAGMENT not in smsg, (
            f"no advisory line expected; got {smsg!r}")
        assert "philosophy.md" in smsg, (
            f"welcome must be intact; got {smsg!r}")
    print("PASS test_marker_absent_no_advisory_line")


def test_advise_script_absent_degrades_gracefully():
    """advise-restart.py absent → both dispatchers exit 0, no traceback, no
    advisory line, welcome intact (graceful degradation, mirror #503)."""
    with tempfile.TemporaryDirectory() as td:
        install_root = _build_install_root(
            Path(td).resolve(), with_advise_script=False)
        # Even with the marker present, an absent script must not crash.
        (install_root / ADVISORY_MARKER).write_text(ADVISORY_REASON)
        stop = _stop(install_root)
        assert stop.returncode == 0, (
            f"stop must exit 0 when advise script absent; "
            f"stderr={stop.stderr!r}")
        assert "Traceback" not in stop.stderr, stop.stderr
        assert ADVISORY_FRAGMENT not in _emission(stop).get("systemMessage", "")
        session = _session(install_root)
        assert session.returncode == 0, (
            f"session must exit 0 when advise script absent; "
            f"stderr={session.stderr!r}")
        assert "Traceback" not in session.stderr, session.stderr
        smsg = _emission(session).get("systemMessage", "")
        assert ADVISORY_FRAGMENT not in smsg, (
            f"no advisory line when script absent; got {smsg!r}")
        assert "philosophy.md" in smsg, (
            f"welcome must survive graceful degradation; got {smsg!r}")
        # The marker is untouched (no clear was possible).
        assert _marker_present(install_root), (
            "absent script must not clear the marker")
    print("PASS test_advise_script_absent_degrades_gracefully")


def main() -> int:
    test_marker_present_stop_emits_advisory_line()
    test_marker_present_session_emits_advisory_and_clears()
    test_marker_absent_no_advisory_line()
    test_advise_script_absent_degrades_gracefully()
    return 0


if __name__ == "__main__":
    sys.exit(main())
