#!/usr/bin/env python3
"""test-tick-log.py — e2e tests for scripts/tick-log.py (Inv 36 / D4,
issue #521).

`tick-log.py` is a minimal append-only JSON-per-line logger to
`.rabbit/tick.log` (state dir via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else
`<cwd>/.rabbit`). One CLI appends `{ts, decision, detail}`.

Scenarios:
  A) one append writes exactly one JSON line carrying ts/decision/detail
  B) a second append APPENDS (file now has two lines)
  C) --help smoke
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
TICKLOG = os.path.join(SCRIPTS, "tick-log.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run(state_dir, decision, detail):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, TICKLOG, "--decision", decision, "--detail", detail],
        capture_output=True, text=True, env=env,
    )


# A — single append
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    proc = run(state_dir, "idle: no work", "queue empty")
    log = os.path.join(state_dir, "tick.log")
    if proc.returncode != 0:
        fail(f"A: tick-log exit {proc.returncode}; err={proc.stderr!r}")
    elif not os.path.isfile(log):
        fail(f"A: tick.log not created at {log}")
    else:
        lines = [ln for ln in open(log).read().splitlines() if ln.strip()]
        if len(lines) != 1:
            fail(f"A: expected 1 log line, got {len(lines)}: {lines!r}")
        else:
            try:
                rec = json.loads(lines[0])
            except json.JSONDecodeError as e:
                rec = None
                fail(f"A: log line is not JSON: {e}")
            if rec is not None:
                if all(k in rec for k in ("ts", "decision", "detail")):
                    ok("A: append wrote one JSON line with ts/decision/detail")
                else:
                    fail(f"A: log record missing fields: {rec!r}")
                if rec.get("decision") == "idle: no work":
                    ok("A: decision field round-trips")
                else:
                    fail(f"A: decision wrong: {rec!r}")

# B — append is additive
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    run(state_dir, "entering", "tick start")
    run(state_dir, "skipped: tick already running", "fresh marker")
    log = os.path.join(state_dir, "tick.log")
    lines = [ln for ln in open(log).read().splitlines() if ln.strip()]
    if len(lines) == 2:
        ok("B: second append is additive (two lines)")
    else:
        fail(f"B: expected 2 lines, got {len(lines)}")

# C — --help smoke
proc = subprocess.run(
    [sys.executable, TICKLOG, "--help"], capture_output=True, text=True,
)
if proc.returncode == 0 and "log" in (proc.stdout + proc.stderr).lower():
    ok("C: --help exits 0 with recognizable usage")
else:
    fail(f"C: --help exit {proc.returncode}; out={proc.stdout!r}")

sys.exit(FAIL)
