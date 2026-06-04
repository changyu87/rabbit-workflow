#!/usr/bin/env python3
"""test-running-guard.py — e2e tests for scripts/running-guard.py
(Inv 35 / D3, issues #521 + #526).

`running-guard.py` inspects `.rabbit-auto-evolve-running` and decides
proceed/skip, clearing a STALE marker. Per the #526 soundness fix, staleness
keys on ACTUAL activity (the `.rabbit/auto-evolve-state.json` mtime within an
IDLE_WINDOW) plus a DURABLE owner PID, combined CONSERVATIVELY: a marker is
STALE only when BOTH (no live owner) AND (state.json idle beyond IDLE_WINDOW
or absent). If EITHER the owner is alive OR activity is recent, the marker is
FRESH and preserved (prefer false-negative). Total elapsed since marker
creation is NO LONGER a staleness signal on its own.

The repo root is the cwd (or `RABBIT_AUTO_EVOLVE_REPO_ROOT`); the activity
window is overridable via `RABBIT_AUTO_EVOLVE_IDLE_SECS` for the test. The
state dir (for both the activity signal and the stale-cleared log line) is
`RABBIT_AUTO_EVOLVE_STATE_DIR`.

Scenarios:
  A) marker absent                          -> proceed, running false
  B) live-owner active (live sentinel pid,
     marker old, no recent state.json)      -> skip, marker preserved
  C) long-active: marker old, NO live pid,
     state.json mtime fresh                 -> skip (NOT stale), preserved
                                               (the #526 false-positive fix)
  D) crashed: dead pid AND state.json idle  -> proceed, stale_cleared, marker
                                               removed, "stale" logged
  E) PID-free marker, state.json idle/absent-> proceed, stale_cleared, removed
                                               (guard functions without a pid)
  F) helper-PID regression: the pid recorded in the marker the shared
     phase-walk writes (Inv 42) is NOT the walk's own transient os.getpid()
     (the marker-content shape lives in start-loop.py's _marker_content,
     imported by the walk)
  G) --help smoke
"""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
GUARD = os.path.join(SCRIPTS, "running-guard.py")
WALK = os.path.join(SCRIPTS, "run-tick-phases.py")
MARKER = ".rabbit-auto-evolve-running"
STATE_REL = os.path.join(".rabbit", "auto-evolve-state.json")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run(repo_root, idle_secs=None):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(repo_root, ".rabbit")
    if idle_secs is not None:
        env["RABBIT_AUTO_EVOLVE_IDLE_SECS"] = str(idle_secs)
    return subprocess.run(
        [sys.executable, GUARD], capture_output=True, text=True, env=env,
    )


def parsed(proc):
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def write_marker(repo_root, content, age_secs=0):
    mpath = os.path.join(repo_root, MARKER)
    with open(mpath, "w") as f:
        f.write(content)
    if age_secs:
        old = time.time() - age_secs
        os.utime(mpath, (old, old))
    return mpath


def write_state(repo_root, age_secs=0):
    """Write a minimal state.json and backdate its mtime by age_secs."""
    spath = os.path.join(repo_root, STATE_REL)
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    with open(spath, "w") as f:
        json.dump({"schema_version": "1.3.0"}, f)
    if age_secs:
        old = time.time() - age_secs
        os.utime(spath, (old, old))
    return spath


# A — absent marker -> proceed, running false
with tempfile.TemporaryDirectory() as d:
    proc = run(d)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "proceed" \
            and j.get("running") is False:
        ok("A: absent marker -> proceed, running false")
    else:
        fail(f"A: expected proceed/running false; out={proc.stdout!r} "
             f"err={proc.stderr!r}")

# B — live-owner active: live sentinel pid, marker old, NO recent state.json.
#     The live owner alone keeps the marker FRESH -> skip, preserved.
with tempfile.TemporaryDirectory() as d:
    sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        write_state(d, age_secs=10_000)  # idle state.json (no activity signal)
        mpath = write_marker(d, f"pid={sentinel.pid} ts=old session",
                             age_secs=10_000)  # very old marker
        proc = run(d, idle_secs=600)
        j = parsed(proc)
        if proc.returncode == 0 and j and j.get("action") == "skip" \
                and j.get("reason") == "tick-running":
            ok("B: live-owner active (old marker) -> skip, NOT stale")
        else:
            fail(f"B: expected skip/tick-running; out={proc.stdout!r} "
                 f"err={proc.stderr!r}")
        if os.path.exists(mpath):
            ok("B: live-owner marker is preserved")
        else:
            fail("B: live-owner marker was wrongly removed")
    finally:
        sentinel.terminate()
        sentinel.wait()

# C — long-active: marker old, NO live pid, but state.json mtime is FRESH
#     (within IDLE_WINDOW). This is the #526 long-active false-positive the
#     fix eliminates: activity keeps it FRESH despite marker age.
with tempfile.TemporaryDirectory() as d:
    write_state(d, age_secs=0)  # state.json touched just now -> active
    mpath = write_marker(d, "pid=999999 ts=old session", age_secs=10_000)
    proc = run(d, idle_secs=600)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "skip" \
            and j.get("reason") == "tick-running":
        ok("C: long-active (old marker, fresh state.json) -> skip, NOT stale")
    else:
        fail(f"C: expected skip/tick-running; out={proc.stdout!r} "
             f"err={proc.stderr!r}")
    if os.path.exists(mpath):
        ok("C: long-active marker is preserved")
    else:
        fail("C: long-active marker was wrongly removed (the #526 bug)")

# D — crashed: dead pid AND state.json idle beyond IDLE_WINDOW -> stale,
#     cleared, "stale" logged.
with tempfile.TemporaryDirectory() as d:
    write_state(d, age_secs=10_000)  # idle
    mpath = write_marker(d, "pid=999999 ts=old session", age_secs=10_000)
    proc = run(d, idle_secs=600)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "proceed" \
            and j.get("stale_cleared") is True:
        ok("D: crashed (dead pid + idle state) -> proceed, stale_cleared")
    else:
        fail(f"D: expected proceed/stale_cleared; out={proc.stdout!r} "
             f"err={proc.stderr!r}")
    if not os.path.exists(mpath):
        ok("D: crashed marker was cleared from disk")
    else:
        fail("D: crashed marker was NOT removed")
    log = os.path.join(d, ".rabbit", "tick.log")
    if os.path.isfile(log) and "stale" in open(log).read().lower():
        ok("D: a 'stale' decision line was logged to .rabbit/tick.log")
    else:
        fail("D: no stale-cleared line logged to .rabbit/tick.log")

# E — PID-free marker, state.json idle -> stale and cleared (guard functions
#     without a pid; the activity signal alone governs).
with tempfile.TemporaryDirectory() as d:
    write_state(d, age_secs=10_000)  # idle
    mpath = write_marker(d, "ts=old session", age_secs=10_000)  # no pid=
    proc = run(d, idle_secs=600)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "proceed" \
            and j.get("stale_cleared") is True:
        ok("E: pid-free idle marker -> proceed, stale_cleared")
    else:
        fail(f"E: expected proceed/stale_cleared; out={proc.stdout!r} "
             f"err={proc.stderr!r}")
    if not os.path.exists(mpath):
        ok("E: pid-free idle marker was cleared from disk")
    else:
        fail("E: pid-free idle marker was NOT removed")

# E2 — PID-free marker but state.json absent entirely -> still stale
with tempfile.TemporaryDirectory() as d:
    mpath = write_marker(d, "ts=old session", age_secs=10_000)  # no state.json
    proc = run(d, idle_secs=600)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "proceed" \
            and j.get("stale_cleared") is True and not os.path.exists(mpath):
        ok("E2: pid-free, no state.json -> proceed, stale_cleared")
    else:
        fail(f"E2: expected proceed/stale_cleared; out={proc.stdout!r} "
             f"err={proc.stderr!r}")

# F — helper-PID regression: the pid recorded in the marker the shared
#     phase-walk writes (Inv 42) must NOT be the walk's own transient
#     os.getpid(). Run run-tick-phases.py pre-dispatch (the real writer), have
#     it report its own pid via the result JSON's process, then read the
#     recorded pid from the marker content.
_F_STUBS = {
    "sync-tree.py": "print('{\"status\": \"synced\"}')",
    "fetch-queue.py": "print('[]')",
    "triage-batch.py": "import sys; sys.stdin.read(); print('[]')",
    "plan-batch.py": "import sys; sys.stdin.read(); print('{}')",
}
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    stub_dir = os.path.join(d, "stubs")
    os.makedirs(repo_root)
    os.makedirs(state_dir)
    os.makedirs(stub_dir)
    for name, body in _F_STUBS.items():
        p = os.path.join(stub_dir, name)
        with open(p, "w") as f:
            f.write(f"#!{sys.executable}\n{body}\n")
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    # Real running-guard + a tick-log stub (running-guard imports it by file).
    import shutil as _sh
    _sh.copy(GUARD, os.path.join(stub_dir, "running-guard.py"))
    with open(os.path.join(stub_dir, "tick-log.py"), "w") as f:
        f.write("def append(decision, detail):\n    pass\n")
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump({"queue": [], "in_flight": []}, f)
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = stub_dir
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    # Wrap the walk so we can capture the walk process's own transient pid.
    child_code = (
        "import os,sys,runpy\n"
        "sys.stderr.write('CHILD_PID=%d\\n' % os.getpid())\n"
        "sys.argv=['run-tick-phases.py','pre-dispatch']\n"
        "runpy.run_path({!r}, run_name='__main__')\n"
    ).format(WALK)
    wl = subprocess.run(
        [sys.executable, "-c", child_code],
        capture_output=True, text=True, env=env,
    )
    m = re.search(r"CHILD_PID=(\d+)", wl.stderr)
    child_pid = int(m.group(1)) if m else None
    mpath = os.path.join(repo_root, MARKER)
    content = open(mpath).read() if os.path.exists(mpath) else ""
    rec = re.search(r"pid=(\d+)", content)
    recorded_pid = int(rec.group(1)) if rec else None
    if not os.path.exists(mpath):
        fail(f"F: the walk did not write the running marker; err={wl.stderr!r}")
    elif child_pid is None:
        fail(f"F: could not capture the walk's transient pid; err={wl.stderr!r}")
    elif recorded_pid is not None and recorded_pid == child_pid:
        fail(f"F: recorded pid {recorded_pid} IS the walk's transient pid "
             f"(the helper-PID bug); content={content!r}")
    else:
        ok(f"F: recorded owner pid ({recorded_pid}) != walk transient "
           f"pid ({child_pid}) — durable owner or pid-free")

# G — --help smoke
proc = subprocess.run(
    [sys.executable, GUARD, "--help"], capture_output=True, text=True,
)
if proc.returncode == 0 and "running" in (proc.stdout + proc.stderr).lower():
    ok("G: --help exits 0 with recognizable usage")
else:
    fail(f"G: --help exit {proc.returncode}; out={proc.stdout!r}")

sys.exit(FAIL)
