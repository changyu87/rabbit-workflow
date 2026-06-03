#!/usr/bin/env python3
"""test-session-start-auto-resume-wired.py — e2e: issue #503.

session-start-dispatcher.py INVOKES rabbit-auto-evolve's
`scripts/check-auto-resume.py` (a contract INVOKE, NOT a cross-feature edit)
and, when that script reports `{"resume": true, "action": ...}`, surfaces the
resume in its SessionStart output:

  - a branded banner line in `systemMessage` so the human sees the resume, AND
  - the `action` command text in `additionalContext` so Claude Code
    auto-executes the resume.

When the script reports `resume: false` (the common case), or when the script
is absent / errors (graceful degradation), the dispatcher output is unchanged:
no resume banner, no resume action injected.

This is an end-to-end test: it builds a fake install root with the deployed
dispatcher and the real check-auto-resume.py, sets the rabbit-auto-evolve
runtime markers on disk, runs the dispatcher as a subprocess, and asserts on
the emitted JSON.
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
CHECK_AUTO_RESUME_SRC = (
    REPO / ".claude/features/rabbit-auto-evolve/scripts/check-auto-resume.py"
)

RESUME_BANNER_FRAGMENT = "Auto-resuming rabbit-auto-evolve"
RESUME_ACTION = "/rabbit-auto-evolve start"

ACTIVE_MARKER = ".rabbit-auto-evolve-active"
RESTART_MARKER = ".rabbit-auto-evolve-restart-needed"
RUNNING_MARKER = ".rabbit-auto-evolve-running"


def _build_install_root(td: Path, *, with_check_script: bool = True) -> Path:
    """Create a fake <install_root> with the deployed dispatcher under
    <install_root>/.claude/hooks/, the contract + rabbit-meta features for
    runtime imports, the rabbit-cage feature.json, a minimal policy source,
    and (optionally) the real check-auto-resume.py at its canonical path."""
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

    if with_check_script:
        ae_scripts = install_root / ".claude/features/rabbit-auto-evolve/scripts"
        ae_scripts.mkdir(parents=True)
        shutil.copy2(CHECK_AUTO_RESUME_SRC, ae_scripts / "check-auto-resume.py")

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


def _emission(proc: subprocess.CompletedProcess) -> dict:
    out = proc.stdout.strip()
    assert out, f"expected JSON on stdout; stderr={proc.stderr!r}"
    return json.loads(out)


def test_resume_true_surfaces_banner_and_action():
    """All three markers set (active + restart-needed, no running) →
    dispatcher surfaces the resume banner AND injects the resume action."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path)
        (install_root / ACTIVE_MARKER).write_text("")
        (install_root / RESTART_MARKER).write_text("")
        proc = _run(install_root)
        assert proc.returncode == 0, (
            f"dispatcher failed: stderr={proc.stderr!r}")
        emission = _emission(proc)
        sysmsg = emission.get("systemMessage", "")
        ctx = emission.get("additionalContext", "")
        assert RESUME_BANNER_FRAGMENT in sysmsg, (
            f"resume banner missing from systemMessage; got {sysmsg!r}")
        assert RESUME_ACTION in ctx, (
            f"resume action {RESUME_ACTION!r} missing from additionalContext; "
            f"got {ctx!r}")
    print("PASS test_resume_true_surfaces_banner_and_action")


def test_resume_false_no_banner_no_action():
    """No markers set → resume:false → no resume banner, no resume action.
    Existing welcome output is otherwise unchanged."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path)
        proc = _run(install_root)
        assert proc.returncode == 0, (
            f"dispatcher failed: stderr={proc.stderr!r}")
        emission = _emission(proc)
        sysmsg = emission.get("systemMessage", "")
        ctx = emission.get("additionalContext", "")
        assert RESUME_BANNER_FRAGMENT not in sysmsg, (
            f"resume banner should be absent; got {sysmsg!r}")
        assert RESUME_ACTION not in ctx, (
            f"resume action should be absent; got {ctx!r}")
        # Existing welcome output still present.
        assert "philosophy.md" in sysmsg, (
            f"existing welcome sublines missing; got {sysmsg!r}")
    print("PASS test_resume_false_no_banner_no_action")


def test_running_marker_suppresses_resume():
    """active + restart-needed BUT running present → resume:false → no
    banner, no action (the script owns this condition; the hook honours it)."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path)
        (install_root / ACTIVE_MARKER).write_text("")
        (install_root / RESTART_MARKER).write_text("")
        (install_root / RUNNING_MARKER).write_text("")
        proc = _run(install_root)
        assert proc.returncode == 0, (
            f"dispatcher failed: stderr={proc.stderr!r}")
        emission = _emission(proc)
        sysmsg = emission.get("systemMessage", "")
        ctx = emission.get("additionalContext", "")
        assert RESUME_BANNER_FRAGMENT not in sysmsg, (
            f"resume banner should be suppressed by running marker; "
            f"got {sysmsg!r}")
        assert RESUME_ACTION not in ctx, (
            f"resume action should be suppressed by running marker; "
            f"got {ctx!r}")
    print("PASS test_running_marker_suppresses_resume")


def test_missing_check_script_degrades_gracefully():
    """check-auto-resume.py absent → dispatcher still exits 0, emits valid
    JSON, surfaces the normal welcome, and no resume banner/action."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path, with_check_script=False)
        # Even with markers present, an absent script must not crash the hook.
        (install_root / ACTIVE_MARKER).write_text("")
        (install_root / RESTART_MARKER).write_text("")
        proc = _run(install_root)
        assert proc.returncode == 0, (
            f"dispatcher must exit 0 when check script is absent; "
            f"stderr={proc.stderr!r}")
        assert "Traceback" not in proc.stderr, (
            f"dispatcher raised when check script absent:\n{proc.stderr}")
        emission = _emission(proc)
        sysmsg = emission.get("systemMessage", "")
        ctx = emission.get("additionalContext", "")
        assert RESUME_BANNER_FRAGMENT not in sysmsg, (
            f"no resume banner when script absent; got {sysmsg!r}")
        assert RESUME_ACTION not in ctx, (
            f"no resume action when script absent; got {ctx!r}")
        assert "philosophy.md" in sysmsg, (
            f"existing welcome must survive graceful degradation; "
            f"got {sysmsg!r}")
    print("PASS test_missing_check_script_degrades_gracefully")


def main() -> int:
    test_resume_true_surfaces_banner_and_action()
    test_resume_false_no_banner_no_action()
    test_running_marker_suppresses_resume()
    test_missing_check_script_degrades_gracefully()
    return 0


if __name__ == "__main__":
    sys.exit(main())
