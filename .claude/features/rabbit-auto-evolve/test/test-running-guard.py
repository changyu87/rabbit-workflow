#!/usr/bin/env python3
"""test-running-guard.py — e2e tests for scripts/running-guard.py
(Inv 35 / D3, issue #521).

`running-guard.py` inspects `.rabbit-auto-evolve-running` and decides
proceed/skip, clearing a STALE marker (mtime older than the max-tick window,
or a dead owner PID). The repo root is the cwd (or
`RABBIT_AUTO_EVOLVE_REPO_ROOT`); the staleness window is overridable via
`RABBIT_AUTO_EVOLVE_MAX_TICK_SECS` for the test. The state dir (for the
stale-cleared log line) is `RABBIT_AUTO_EVOLVE_STATE_DIR`.

Scenarios:
  A) marker absent              -> action proceed, running false
  B) fresh marker               -> action skip, reason tick-running
  C) mtime-aged marker (window shrunk to 0) -> proceed, stale_cleared true,
     marker REMOVED, and a "stale" line appended to .rabbit/tick.log
  D) --help smoke
"""

import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
GUARD = os.path.join(SCRIPTS, "running-guard.py")
MARKER = ".rabbit-auto-evolve-running"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run(repo_root, max_secs=None):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(repo_root, ".rabbit")
    if max_secs is not None:
        env["RABBIT_AUTO_EVOLVE_MAX_TICK_SECS"] = str(max_secs)
    return subprocess.run(
        [sys.executable, GUARD], capture_output=True, text=True, env=env,
    )


def parsed(proc):
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


# A — absent
with tempfile.TemporaryDirectory() as d:
    proc = run(d)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "proceed" \
            and j.get("running") is False:
        ok("A: absent marker -> proceed, running false")
    else:
        fail(f"A: expected proceed/running false; out={proc.stdout!r} "
             f"err={proc.stderr!r}")

# B — fresh marker (default large window) -> skip
with tempfile.TemporaryDirectory() as d:
    with open(os.path.join(d, MARKER), "w") as f:
        f.write(f"pid={os.getpid()} ts=now")
    proc = run(d, max_secs=1800)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "skip" \
            and j.get("reason") == "tick-running":
        ok("B: fresh marker -> skip, reason tick-running")
    else:
        fail(f"B: expected skip/tick-running; out={proc.stdout!r} "
             f"err={proc.stderr!r}")
    if os.path.exists(os.path.join(d, MARKER)):
        ok("B: fresh marker is preserved")
    else:
        fail("B: fresh marker was wrongly removed")

# C — mtime-aged marker (window 0 -> any age is stale) -> proceed + cleared
with tempfile.TemporaryDirectory() as d:
    mpath = os.path.join(d, MARKER)
    with open(mpath, "w") as f:
        f.write("pid=999999 ts=old")
    # Backdate mtime so even a 0-second window sees it as stale.
    old = time.time() - 10
    os.utime(mpath, (old, old))
    proc = run(d, max_secs=0)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("action") == "proceed" \
            and j.get("stale_cleared") is True:
        ok("C: stale marker -> proceed, stale_cleared true")
    else:
        fail(f"C: expected proceed/stale_cleared; out={proc.stdout!r} "
             f"err={proc.stderr!r}")
    if not os.path.exists(mpath):
        ok("C: stale marker was cleared from disk")
    else:
        fail("C: stale marker was NOT removed")
    log = os.path.join(d, ".rabbit", "tick.log")
    if os.path.isfile(log) and "stale" in open(log).read().lower():
        ok("C: a 'stale' decision line was logged to .rabbit/tick.log")
    else:
        fail("C: no stale-cleared line logged to .rabbit/tick.log")

# D — --help smoke
proc = subprocess.run(
    [sys.executable, GUARD, "--help"], capture_output=True, text=True,
)
if proc.returncode == 0 and "running" in (proc.stdout + proc.stderr).lower():
    ok("D: --help exits 0 with recognizable usage")
else:
    fail(f"D: --help exit {proc.returncode}; out={proc.stdout!r}")

sys.exit(FAIL)
