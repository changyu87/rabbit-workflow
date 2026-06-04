#!/usr/bin/env python3
"""test-advise-restart.py — spec Inv 52 (added v0.42.0 for issue #545).

End-to-end tests for `scripts/advise-restart.py`, the advisory-restart marker
lifecycle script. The advisory marker `.rabbit-auto-evolve-restart-advised` is
a structured, persistently-surfaced restart signal that mirrors the HARD
`.rabbit-auto-evolve-restart-needed` marker but is ADVISORY — it never pauses,
blocks, holds, or auto-resumes the loop.

Three subcommands:

  - write "<reason>"  -> writes the marker at the repo root with the structured
                         reason as its content; overwrites if present (latest
                         reason wins). Missing reason -> non-zero exit.
  - status            -> emits JSON on stdout (always exit 0):
                           present: {"advised": true,  "reason": "<content>"}
                           absent:  {"advised": false}
  - clear             -> removes the marker; idempotent (missing -> exit 0).

The script honors RABBIT_AUTO_EVOLVE_REPO_ROOT for test isolation and reads/
writes files only, so status/clear exit codes are always 0.

These drive the real script as a subprocess against seeded marker fixtures,
exactly as rabbit-cage's Stop/SessionStart dispatcher (Part B, separate
feature) will INVOKE it. They also pin the strict-separation contract: the
advisory path NEVER writes/affects the hard `.rabbit-auto-evolve-restart-needed`
marker and never pauses the tick.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "advise-restart.py"

ADVISED = ".rabbit-auto-evolve-restart-advised"
HARD = ".rabbit-auto-evolve-restart-needed"
RUNNING = ".rabbit-auto-evolve-running"
ABORTED = ".rabbit-auto-evolve-aborted"


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


def _run(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
    )


print("test-advise-restart.py")

# --- t0: script exists ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")

# --- t1: write creates the marker with the reason as content ---
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    reason = "activates skill-creator + code-review; enables worktree.baseRef"
    r = _run(td, ["write", reason])
    marker = td / ADVISED
    if r.returncode != 0:
        fail_t("write/create", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif not marker.is_file():
        fail_t("write/create", f"marker not created: {ADVISED}")
    elif marker.read_text() != reason:
        fail_t("write/create",
               f"content mismatch: expected {reason!r}, got {marker.read_text()!r}")
    else:
        ok("write/create", f"{ADVISED} content={reason!r}")

# --- t2: write overwrites (latest reason wins) ---
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    r1 = _run(td, ["write", "first reason"])
    r2 = _run(td, ["write", "second reason"])
    actual = (td / ADVISED).read_text() if (td / ADVISED).is_file() else None
    if r1.returncode != 0 or r2.returncode != 0:
        fail_t("write/overwrite",
               f"non-zero exits: r1={r1.returncode}; r2={r2.returncode}")
    elif actual != "second reason":
        fail_t("write/overwrite", f"expected 'second reason', got {actual!r}")
    else:
        ok("write/overwrite", "latest reason wins")

# --- t3: write rejects missing reason argument ---
with tempfile.TemporaryDirectory() as d:
    r = _run(Path(d), ["write"])
    if r.returncode == 0:
        fail_t("write/missing-arg", "expected non-zero exit when reason omitted")
    else:
        ok("write/missing-arg", f"exit {r.returncode}")

# --- t4: status reports advised:true + reason when present ---
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    reason = "restart unlocks parallel dispatch"
    (td / ADVISED).write_text(reason)
    r = _run(td, ["status"])
    if r.returncode != 0:
        fail_t("status/present", f"exit {r.returncode} (want 0); stderr={r.stderr!r}")
    else:
        try:
            obj = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            obj = None
            fail_t("status/present", f"stdout not JSON: {e}; stdout={r.stdout!r}")
        if obj is not None:
            if obj.get("advised") is not True:
                fail_t("status/present", f"advised={obj.get('advised')!r} (want True)")
            elif obj.get("reason") != reason:
                fail_t("status/present", f"reason={obj.get('reason')!r} (want {reason!r})")
            else:
                ok("status/present", f"advised=True reason={reason!r} exit=0")

# --- t5: status reports advised:false when absent (graceful) ---
with tempfile.TemporaryDirectory() as d:
    r = _run(Path(d), ["status"])
    if r.returncode != 0:
        fail_t("status/absent", f"exit {r.returncode} (want 0); stderr={r.stderr!r}")
    else:
        try:
            obj = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            obj = None
            fail_t("status/absent", f"stdout not JSON: {e}; stdout={r.stdout!r}")
        if obj is not None:
            if obj.get("advised") is not False:
                fail_t("status/absent", f"advised={obj.get('advised')!r} (want False)")
            else:
                ok("status/absent", "advised=False exit=0")

# --- t6: clear removes the marker ---
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    (td / ADVISED).write_text("some reason")
    r = _run(td, ["clear"])
    if r.returncode != 0:
        fail_t("clear/removes", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif (td / ADVISED).exists():
        fail_t("clear/removes", "marker still present after clear")
    else:
        ok("clear/removes", "marker removed")

# --- t7: clear is idempotent (missing marker -> exit 0) ---
with tempfile.TemporaryDirectory() as d:
    r = _run(Path(d), ["clear"])
    if r.returncode != 0:
        fail_t("clear/idempotent",
               f"expected exit 0 when marker absent, got {r.returncode}; "
               f"stderr={r.stderr!r}")
    else:
        ok("clear/idempotent", "missing marker is no-op")

# --- t8: strict separation — write NEVER touches the hard marker ---
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    r = _run(td, ["write", "advisory only"])
    if r.returncode != 0:
        fail_t("separation/write-no-hard", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif (td / HARD).exists():
        fail_t("separation/write-no-hard",
               "advisory write created the HARD restart-needed marker")
    elif (td / RUNNING).exists() or (td / ABORTED).exists():
        fail_t("separation/write-no-hard",
               "advisory write created running/aborted marker")
    else:
        ok("separation/write-no-hard",
           "advisory write left hard/running/aborted markers untouched")

# --- t9: strict separation — clear NEVER removes the hard marker ---
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    (td / ADVISED).write_text("advisory reason")
    (td / HARD).write_text("hard restart reason")
    r = _run(td, ["clear"])
    if r.returncode != 0:
        fail_t("separation/clear-keeps-hard", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif (td / ADVISED).exists():
        fail_t("separation/clear-keeps-hard", "advisory marker not cleared")
    elif not (td / HARD).is_file():
        fail_t("separation/clear-keeps-hard",
               "clear removed the HARD restart-needed marker")
    elif (td / HARD).read_text() != "hard restart reason":
        fail_t("separation/clear-keeps-hard", "hard marker content was altered")
    else:
        ok("separation/clear-keeps-hard",
           "clear removed only the advisory marker; hard marker intact")

# --- t10: status NEVER reads/conflates the hard marker ---
# Hard marker present, advisory absent -> status must still report advised:false.
with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    (td / HARD).write_text("hard restart reason")
    r = _run(td, ["status"])
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("separation/status-ignores-hard", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif obj is None:
        fail_t("separation/status-ignores-hard", f"stdout not JSON: {r.stdout!r}")
    elif obj.get("advised") is not False:
        fail_t("separation/status-ignores-hard",
               f"advised={obj.get('advised')!r} with only the HARD marker present "
               "(advisory status must not conflate the hard marker)")
    else:
        ok("separation/status-ignores-hard",
           "status reports advised=False when only the hard marker is present")

# --- t11: --help smoke -> exit 0 with usage text ---
with tempfile.TemporaryDirectory() as d:
    r = _run(Path(d), ["--help"])
    if r.returncode == 0 and (
        "usage" in r.stdout.lower() or "advis" in r.stdout.lower()
    ):
        ok("help", "exit 0 with recognizable usage text")
    else:
        fail_t("help", f"exit {r.returncode}; stdout={r.stdout!r}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
