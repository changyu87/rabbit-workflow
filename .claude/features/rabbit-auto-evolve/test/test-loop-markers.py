#!/usr/bin/env python3
"""test-loop-markers.py — e2e tests for the marker-writing/deleting scripts.

Per spec Inv 17, rabbit-auto-evolve owns five runtime markers whose writes
are wrapped in dedicated scripts (so scope-guard does not see the literal
.rabbit-auto-evolve-* path in the Bash command string):

  - scripts/start-loop.py            -> writes .rabbit-auto-evolve-running         (content "session")
  - scripts/end-tick.py              -> deletes .rabbit-auto-evolve-running        (Inv 20)
  - scripts/stop-loop.py             -> writes .rabbit-auto-evolve-stop-requested  (content "session")
  - scripts/mark-restart-needed.py R -> writes .rabbit-auto-evolve-restart-needed  (content R)
  - scripts/mark-aborted.py R        -> writes .rabbit-auto-evolve-aborted         (content R)

Each script honors RABBIT_AUTO_EVOLVE_REPO_ROOT (or cwd default) for repo
discovery. Idempotency: re-invoking with the same args is a no-op; differing
content overwrites.

Per spec Inv 19 (start-loop self-heal), `start-loop.py` ALSO:
  1. Deletes any stale `.rabbit-auto-evolve-stop-requested` marker.
  2. Bootstraps `.rabbit/auto-evolve-state.json` with default content
     if the file is missing, empty, or fails JSON parse — atomically
     via temp+rename. A valid existing state file is left untouched.

Per spec Inv 20 (end-tick), `end-tick.py` deletes the running marker on
every tick exit path. Idempotent: missing marker is a no-op (exit 0).
"""

from __future__ import annotations

import json
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

# --- t7: Inv 19 — start-loop.py cancels a pending stop marker ---
start_loop = SCRIPTS_DIR / "start-loop.py"
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    stop_marker = td_path / ".rabbit-auto-evolve-stop-requested"
    stop_marker.write_text("session")
    r = _run(start_loop, [], td_path)
    if r.returncode != 0:
        fail_t("start-self-heal/cancel-stop",
               f"exit {r.returncode}; stderr={r.stderr!r}")
    elif not (td_path / ".rabbit-auto-evolve-running").is_file():
        fail_t("start-self-heal/cancel-stop", "running marker not written")
    elif stop_marker.exists():
        fail_t("start-self-heal/cancel-stop",
               "stop-requested marker still present after start-loop")
    else:
        ok("start-self-heal/cancel-stop",
           "start-loop deletes stale stop marker AND writes running")

# --- t8: Inv 19 — start-loop.py bootstraps missing state file ---
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    state_path = td_path / ".rabbit" / "auto-evolve-state.json"
    # No .rabbit/ directory at all.
    r = _run(start_loop, [], td_path)
    if r.returncode != 0:
        fail_t("start-self-heal/bootstrap-missing",
               f"exit {r.returncode}; stderr={r.stderr!r}")
    elif not state_path.is_file():
        fail_t("start-self-heal/bootstrap-missing",
               f"state file not created at {state_path}")
    else:
        try:
            data = json.loads(state_path.read_text())
        except json.JSONDecodeError as e:
            fail_t("start-self-heal/bootstrap-missing",
                   f"state file is not valid JSON: {e}")
            data = None
        if data is not None:
            if data.get("schema_version") != "1.2.0":
                fail_t("start-self-heal/bootstrap-missing",
                       f"schema_version != '1.2.0': {data.get('schema_version')!r}")
            elif data.get("queue") != [] or data.get("in_flight") != []:
                fail_t("start-self-heal/bootstrap-missing",
                       f"queue/in_flight not empty: queue={data.get('queue')!r}, "
                       f"in_flight={data.get('in_flight')!r}")
            elif data.get("restart_needed") is not None:
                fail_t("start-self-heal/bootstrap-missing",
                       f"restart_needed should be null: {data.get('restart_needed')!r}")
            elif data.get("stop_requested") is not False:
                fail_t("start-self-heal/bootstrap-missing",
                       f"stop_requested should be False: {data.get('stop_requested')!r}")
            else:
                ok("start-self-heal/bootstrap-missing",
                   "default state file written with schema_version=1.2.0")

# --- t9: Inv 19 — start-loop.py recovers an empty state file ---
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    state_dir = td_path / ".rabbit"
    state_dir.mkdir()
    state_path = state_dir / "auto-evolve-state.json"
    state_path.write_text("")
    r = _run(start_loop, [], td_path)
    if r.returncode != 0:
        fail_t("start-self-heal/recover-empty",
               f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            data = json.loads(state_path.read_text())
        except json.JSONDecodeError as e:
            fail_t("start-self-heal/recover-empty",
                   f"state file still invalid after start-loop: {e}")
        else:
            if data.get("schema_version") == "1.2.0":
                ok("start-self-heal/recover-empty",
                   "empty state file replaced with default")
            else:
                fail_t("start-self-heal/recover-empty",
                       f"schema_version != '1.2.0': {data.get('schema_version')!r}")

# --- t10: Inv 19 — start-loop.py recovers a malformed state file ---
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    state_dir = td_path / ".rabbit"
    state_dir.mkdir()
    state_path = state_dir / "auto-evolve-state.json"
    state_path.write_text("not json {{{")
    r = _run(start_loop, [], td_path)
    if r.returncode != 0:
        fail_t("start-self-heal/recover-malformed",
               f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        try:
            data = json.loads(state_path.read_text())
        except json.JSONDecodeError as e:
            fail_t("start-self-heal/recover-malformed",
                   f"state file still invalid after start-loop: {e}")
        else:
            if data.get("schema_version") == "1.2.0":
                ok("start-self-heal/recover-malformed",
                   "malformed state file replaced with default")
            else:
                fail_t("start-self-heal/recover-malformed",
                       f"schema_version != '1.2.0': {data.get('schema_version')!r}")

# --- t11: Inv 19 — start-loop.py preserves a valid non-default state file ---
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    state_dir = td_path / ".rabbit"
    state_dir.mkdir()
    state_path = state_dir / "auto-evolve-state.json"
    custom_state = {
        "schema_version": "1.0.0",
        "updated_at": "2026-06-02T12:34:56Z",
        "queue": [{"issue": 123, "decision": "work", "feature": "foo"}],
        "in_flight": [456],
        "last_merged_sha": "deadbeef",
        "last_tagged_version": "v0.9.0",
        "consecutive_failures": 2,
        "stop_requested": False,
        "restart_needed": None,
    }
    state_path.write_text(json.dumps(custom_state, indent=2))
    r = _run(start_loop, [], td_path)
    if r.returncode != 0:
        fail_t("start-self-heal/preserve-valid",
               f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        data = json.loads(state_path.read_text())
        if data == custom_state:
            ok("start-self-heal/preserve-valid",
               "valid state file left unchanged")
        else:
            fail_t("start-self-heal/preserve-valid",
                   f"valid state file was modified: {data!r}")

# --- t12: Inv 20 — end-tick.py exists ---
end_tick = SCRIPTS_DIR / "end-tick.py"
if end_tick.is_file():
    ok("exists/end-tick.py", str(end_tick))
else:
    fail_t("exists/end-tick.py", f"script not found: {end_tick}")

# --- t13: Inv 20 — end-tick.py deletes the running marker ---
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    running = td_path / ".rabbit-auto-evolve-running"
    running.write_text("session")
    r = _run(end_tick, [], td_path)
    if r.returncode != 0:
        fail_t("end-tick/delete-running",
               f"exit {r.returncode}; stderr={r.stderr!r}")
    elif running.exists():
        fail_t("end-tick/delete-running",
               "running marker still present after end-tick")
    else:
        ok("end-tick/delete-running", "running marker deleted")

# --- t14: Inv 20 — end-tick.py is idempotent (missing marker -> exit 0) ---
with tempfile.TemporaryDirectory() as td:
    td_path = Path(td)
    r = _run(end_tick, [], td_path)
    if r.returncode != 0:
        fail_t("end-tick/idempotent",
               f"expected exit 0 when marker absent, got {r.returncode}; "
               f"stderr={r.stderr!r}")
    else:
        ok("end-tick/idempotent", "missing marker is no-op")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
