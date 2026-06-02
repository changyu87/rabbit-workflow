#!/usr/bin/env python3
"""test-loop-markers.py — e2e tests for the four marker-writing scripts.

Per spec Inv 17, rabbit-auto-evolve owns four runtime markers whose writes
are wrapped in dedicated scripts (so scope-guard does not see the literal
.rabbit-auto-evolve-* path in the Bash command string):

  - scripts/start-loop.py            -> .rabbit-auto-evolve-running         (content "session")
  - scripts/stop-loop.py             -> .rabbit-auto-evolve-stop-requested  (content "session")
  - scripts/mark-restart-needed.py R -> .rabbit-auto-evolve-restart-needed  (content R)
  - scripts/mark-aborted.py R        -> .rabbit-auto-evolve-aborted         (content R)

Each script honors RABBIT_AUTO_EVOLVE_REPO_ROOT (or cwd default) for repo
discovery. Idempotency: re-invoking with the same args is a no-op; differing
content overwrites.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = FEATURE_DIR / "scripts"

NO_ARG_SCRIPTS = [
    ("start-loop.py", ".rabbit-auto-evolve-running", "session"),
    ("stop-loop.py", ".rabbit-auto-evolve-stop-requested", "session"),
]
REASON_SCRIPTS = [
    ("mark-restart-needed.py", ".rabbit-auto-evolve-restart-needed"),
    ("mark-aborted.py", ".rabbit-auto-evolve-aborted"),
]


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


def _run(script: Path, args: list[str], repo_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, str(script), *args],
        env=env,
        capture_output=True,
        text=True,
    )


print("test-loop-markers.py")

# --- t1: scripts exist on disk ---
for name, _, _ in NO_ARG_SCRIPTS:
    p = SCRIPTS_DIR / name
    if p.is_file():
        ok(f"exists/{name}", str(p))
    else:
        fail_t(f"exists/{name}", f"script not found: {p}")
for name, _ in REASON_SCRIPTS:
    p = SCRIPTS_DIR / name
    if p.is_file():
        ok(f"exists/{name}", str(p))
    else:
        fail_t(f"exists/{name}", f"script not found: {p}")

# --- t2: no-arg scripts (start-loop, stop-loop) write the right marker ---
for name, marker, expected_content in NO_ARG_SCRIPTS:
    script = SCRIPTS_DIR / name
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        r = _run(script, [], td_path)
        if r.returncode != 0:
            fail_t(f"write/{name}", f"exit {r.returncode}; stderr={r.stderr!r}")
            continue
        m = td_path / marker
        if not m.is_file():
            fail_t(f"write/{name}", f"marker not created: {marker}")
            continue
        actual = m.read_text()
        if actual != expected_content:
            fail_t(
                f"write/{name}",
                f"marker content mismatch: expected {expected_content!r}, got {actual!r}",
            )
            continue
        ok(f"write/{name}", f"{marker} content={expected_content!r}")

# --- t3: reason scripts write the marker with reason as content ---
for name, marker in REASON_SCRIPTS:
    script = SCRIPTS_DIR / name
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        reason = f"unit test reason for {name}"
        r = _run(script, [reason], td_path)
        if r.returncode != 0:
            fail_t(f"write/{name}", f"exit {r.returncode}; stderr={r.stderr!r}")
            continue
        m = td_path / marker
        if not m.is_file():
            fail_t(f"write/{name}", f"marker not created: {marker}")
            continue
        actual = m.read_text()
        if actual != reason:
            fail_t(
                f"write/{name}",
                f"marker content mismatch: expected {reason!r}, got {actual!r}",
            )
            continue
        ok(f"write/{name}", f"{marker} content={reason!r}")

# --- t4: idempotency — re-run with same args is no-op (no error, marker unchanged) ---
for name, marker, expected_content in NO_ARG_SCRIPTS:
    script = SCRIPTS_DIR / name
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        r1 = _run(script, [], td_path)
        r2 = _run(script, [], td_path)
        if r1.returncode != 0 or r2.returncode != 0:
            fail_t(
                f"idempotent/{name}",
                f"non-zero exits: r1={r1.returncode} stderr={r1.stderr!r}; "
                f"r2={r2.returncode} stderr={r2.stderr!r}",
            )
            continue
        actual = (td_path / marker).read_text()
        if actual != expected_content:
            fail_t(
                f"idempotent/{name}",
                f"after re-run content mismatch: expected {expected_content!r}, got {actual!r}",
            )
            continue
        ok(f"idempotent/{name}", f"re-run no-op")

for name, marker in REASON_SCRIPTS:
    script = SCRIPTS_DIR / name
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        reason = "same reason"
        r1 = _run(script, [reason], td_path)
        r2 = _run(script, [reason], td_path)
        if r1.returncode != 0 or r2.returncode != 0:
            fail_t(
                f"idempotent/{name}",
                f"non-zero exits: r1={r1.returncode} stderr={r1.stderr!r}; "
                f"r2={r2.returncode} stderr={r2.stderr!r}",
            )
            continue
        actual = (td_path / marker).read_text()
        if actual != reason:
            fail_t(
                f"idempotent/{name}",
                f"after re-run content mismatch: expected {reason!r}, got {actual!r}",
            )
            continue
        ok(f"idempotent/{name}", f"re-run no-op")

# --- t5: differing content overwrites ---
for name, marker in REASON_SCRIPTS:
    script = SCRIPTS_DIR / name
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        r1 = _run(script, ["first reason"], td_path)
        r2 = _run(script, ["second reason"], td_path)
        if r1.returncode != 0 or r2.returncode != 0:
            fail_t(
                f"overwrite/{name}",
                f"non-zero exits: r1={r1.returncode}; r2={r2.returncode}",
            )
            continue
        actual = (td_path / marker).read_text()
        if actual != "second reason":
            fail_t(
                f"overwrite/{name}",
                f"expected 'second reason', got {actual!r}",
            )
            continue
        ok(f"overwrite/{name}", f"new content replaces old")

# --- t6: reason scripts reject missing positional arg ---
for name, _ in REASON_SCRIPTS:
    script = SCRIPTS_DIR / name
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        r = _run(script, [], td_path)
        if r.returncode == 0:
            fail_t(
                f"missing-arg/{name}",
                "expected non-zero exit when reason omitted",
            )
            continue
        ok(f"missing-arg/{name}", f"exit {r.returncode}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
