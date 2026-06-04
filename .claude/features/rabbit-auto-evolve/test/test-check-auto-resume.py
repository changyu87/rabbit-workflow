#!/usr/bin/env python3
"""test-check-auto-resume.py — spec Inv 31 (added v0.19.0 for issue #424).

`scripts/check-auto-resume.py` owns mechanical restart-resume detection.
Inspects rabbit-auto-evolve's runtime markers at the repo root and emits a
JSON object on stdout describing whether the loop should auto-resume. Always
exits 0.

Auto-resume conditions (ALL three must hold for resume: true):
  1. .rabbit-auto-evolve-active present (mode is on), AND
  2. .rabbit-auto-evolve-restart-needed present (a restart was needed), AND
  3. .rabbit-auto-evolve-running NOT present (no tick already running).

When all three hold:  {"resume": true,  "action": "/rabbit-auto-evolve start"}
otherwise:            {"resume": false, "action": null}

The script honors RABBIT_AUTO_EVOLVE_REPO_ROOT for test isolation and reads
files only (never invokes ls / test -f), so exit code is always 0.

This is the e2e regression test for the auto-resume conditions: it drives the
real script as a subprocess against seeded marker fixtures, exactly as the
SessionStart hook (rabbit-cage, separate touch) will invoke it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "check-auto-resume.py"

ACTIVE = ".rabbit-auto-evolve-active"
RUNNING = ".rabbit-auto-evolve-running"
RESTART = ".rabbit-auto-evolve-restart-needed"

RESUME_ACTION = "/rabbit-auto-evolve start"


pass_n = 0
fail_n = 0


def ok(t: str, msg: str) -> None:
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t: str, msg: str) -> None:
    global fail_n
    print(f"  FAIL {t}: {msg}")
    fail_n += 1


def _run(repo_root: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(extra or [])],
        env=env,
        capture_output=True,
        text=True,
    )


def _seed(td: Path, names: list[str], content: str = "session") -> None:
    for n in names:
        (td / n).write_text(content)


def _check_case(label: str, markers: list[str], want_resume: bool) -> None:
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        _seed(td, markers)
        cp = _run(td)
        if cp.returncode != 0:
            fail_t(label, f"exit {cp.returncode} (want 0); stderr={cp.stderr!r}")
            return
        try:
            obj = json.loads(cp.stdout)
        except json.JSONDecodeError as e:
            fail_t(label, f"stdout not JSON: {e}; stdout={cp.stdout!r}")
            return
        if obj.get("resume") is not want_resume:
            fail_t(label, f"resume={obj.get('resume')!r} (want {want_resume!r})")
            return
        want_action = RESUME_ACTION if want_resume else None
        if obj.get("action") != want_action:
            fail_t(label, f"action={obj.get('action')!r} (want {want_action!r})")
            return
        ok(label, f"resume={want_resume} action={want_action!r} exit=0")


print("test-check-auto-resume.py")

# --- t0: script exists ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")

# --- t0b: spec Inv 31 documents the three auto-resume conditions ---
# Dual-read (issue #399): prefer the flat docs/spec.md layout, fall back to
# specs/spec.md, then legacy docs/spec/spec.md.
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"
spec_low = SPEC_MD.read_text().lower()
SPEC_REQUIRED = [
    "check-auto-resume.py",
    ".rabbit-auto-evolve-active",
    ".rabbit-auto-evolve-restart-needed",
    ".rabbit-auto-evolve-running",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail_t("spec-inv31", f"spec.md missing auto-resume phrase(s): {missing!r}")
else:
    ok("spec-inv31", "spec.md documents the three auto-resume conditions (Inv 31)")

# --- t1: all three conditions met -> resume ---
_check_case("all-met", [ACTIVE, RESTART], want_resume=True)

# --- t2: active + restart-needed BUT running present -> no resume ---
_check_case("running-blocks", [ACTIVE, RESTART, RUNNING], want_resume=False)

# --- t3: active present, restart-needed absent -> no resume ---
_check_case("no-restart-needed", [ACTIVE], want_resume=False)

# --- t4: active absent (mode off) -> no resume even with restart-needed ---
_check_case("not-active", [RESTART], want_resume=False)

# --- t5: nothing present (clean repo) -> no resume ---
_check_case("clean", [], want_resume=False)

# --- t6: --help smoke -> exit 0 with usage text ---
with tempfile.TemporaryDirectory() as d:
    cp = _run(Path(d), extra=["--help"])
    if cp.returncode == 0 and (
        "resume" in cp.stdout.lower() or "usage" in cp.stdout.lower()
    ):
        ok("help", "exit 0 with recognizable usage text")
    else:
        fail_t("help", f"exit {cp.returncode}; stdout={cp.stdout!r}")

print(f"\n{pass_n} passed, {fail_n} failed")
sys.exit(1 if fail_n else 0)
