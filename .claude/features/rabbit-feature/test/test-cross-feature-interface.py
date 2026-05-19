#!/usr/bin/env python3
"""Smoke test locking the rabbit-feature -> tdd-subagent cross-feature script interface.

Runs `--help` on the two tdd-subagent scripts that rabbit-feature's
`rabbit-feature-touch` skill invokes. Both must exit 0 and emit recognizable
usage text. Any rename, removed flag, or signature break in those scripts
fails this test and forces rabbit-feature into red state (spec Inv 3).

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
TDD_STEP = REPO_ROOT / ".claude/features/tdd-subagent/scripts/tdd-step.py"
DISPATCH = REPO_ROOT / ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py"


def _check_help(script: Path) -> None:
    assert script.exists(), f"missing cross-feature script: {script}"
    result = subprocess.run(
        ["python3", str(script), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{script.name} --help exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Spec Inv 3 requires "recognizable usage text"; argparse-style scripts
    # write to stdout, hand-rolled scripts may write to stderr. Either is
    # acceptable for the cross-feature interface lock.
    combined = result.stdout + result.stderr
    assert "usage:" in combined, (
        f"{script.name} --help did not print 'usage:' on stdout or stderr\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_tdd_step_help() -> None:
    _check_help(TDD_STEP)


def test_dispatch_tdd_subagent_help() -> None:
    _check_help(DISPATCH)


def main() -> int:
    tests = [test_tdd_step_help, test_dispatch_tdd_subagent_help]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
