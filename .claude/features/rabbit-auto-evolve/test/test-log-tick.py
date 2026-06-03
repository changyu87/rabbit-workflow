#!/usr/bin/env python3
"""test-log-tick.py — e2e tests for scripts/log-tick.py + scripts/log-path.py
(Inv 37, issue #404).

`log-tick.py` is the FULL per-tick observability logger (distinct from the
minimal Inv 36 `tick-log.py`). It owns ALL writes to
`<state_dir>/auto-evolve.log` (state dir via `RABBIT_AUTO_EVOLVE_STATE_DIR`,
else `<cwd>/.rabbit`). One CLI call emits AT MOST ONE JSON line.

Each call carries a `--record-kind` classifier; the configured verbosity
level decides whether that kind is emitted (strictly-additive levels):
  quiet  = {tick-start, tick-end}
  normal = quiet + {phase}                (DEFAULT)
  debug  = normal + {phase-transition}

The enable flag + level live in rabbit-auto-evolve's OWN config
(`<state_dir>/auto-evolve-log-config.json`), mutated by `log-tick.py
config ...`. When the enable flag is off, NOTHING is written.

Scenarios:
  A) 100 ticks at quiet/normal/debug → per-level line counts match.
  B) Rotation: write past the 5 MB cap → rotation fires, ≤ 4 files total.
  C) `log off` (enable flag false) → zero file growth across repeated calls.
  D) Each emitted line is < 2 KB (large array payloads truncated, not dropped).
  E) `log-path.py` prints the resolved `.rabbit/auto-evolve.log` path.
  F) `--help` smoke for both scripts: exit 0 with recognizable usage text.
  G) Record carries the minimum spec keys.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
LOGTICK = os.path.join(SCRIPTS, "log-tick.py")
LOGPATH = os.path.join(SCRIPTS, "log-path.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def env_for(state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return env


def run_config(state_dir, *args):
    return subprocess.run(
        [sys.executable, LOGTICK, "config", *args],
        capture_output=True, text=True, env=env_for(state_dir),
    )


def emit(state_dir, record_kind, **fields):
    """Invoke one log-tick.py emit with the given record-kind + fields."""
    argv = [sys.executable, LOGTICK, "emit", "--record-kind", record_kind]
    for k, v in fields.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    return subprocess.run(
        argv, capture_output=True, text=True, env=env_for(state_dir),
    )


def log_lines(state_dir):
    log = os.path.join(state_dir, "auto-evolve.log")
    if not os.path.isfile(log):
        return []
    return [ln for ln in open(log).read().splitlines() if ln.strip()]


def write_one_tick(state_dir, tick):
    """Emit the four record kinds a single tick produces."""
    emit(state_dir, "tick-start", tick=tick, session_id="s1",
         phase_reached="0", phase_result="ok", queue_len=3,
         next_action="fetch")
    emit(state_dir, "phase", tick=tick, session_id="s1",
         phase_reached="2", phase_result="ok", queue_len=3,
         next_action="triage")
    emit(state_dir, "phase-transition", tick=tick, session_id="s1",
         phase_reached="3", phase_result="ok", queue_len=3,
         next_action="plan")
    emit(state_dir, "tick-end", tick=tick, session_id="s1",
         phase_reached="11", phase_result="ok", queue_len=3,
         next_action="idle")


# --- A: per-level line counts over 100 ticks ---------------------------
# Per tick we emit: tick-start, phase, phase-transition, tick-end.
#   quiet  keeps {tick-start, tick-end}            -> 2 / tick -> 200
#   normal keeps {tick-start, tick-end, phase}     -> 3 / tick -> 300
#   debug  keeps all four                          -> 4 / tick -> 400
EXPECTED = {"quiet": 200, "normal": 300, "debug": 400}
for level, expected in EXPECTED.items():
    with tempfile.TemporaryDirectory() as d:
        state_dir = os.path.join(d, ".rabbit")
        os.makedirs(state_dir, exist_ok=True)
        cfg = run_config(state_dir, "level", level)
        if cfg.returncode != 0:
            fail(f"A[{level}]: config level exit {cfg.returncode}; "
                 f"err={cfg.stderr!r}")
            continue
        for t in range(100):
            write_one_tick(state_dir, t)
        n = len(log_lines(state_dir))
        if n == expected:
            ok(f"A[{level}]: 100 ticks → {n} lines (additive verbosity)")
        else:
            fail(f"A[{level}]: expected {expected} lines, got {n}")

# --- B: rotation past 5 MB --------------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    os.makedirs(state_dir, exist_ok=True)
    run_config(state_dir, "level", "debug")
    log = os.path.join(state_dir, "auto-evolve.log")
    # Pre-fill the live log just over 5 MB, then trigger rotation at tick start.
    with open(log, "w") as f:
        f.write("x" * (5 * 1024 * 1024 + 10) + "\n")
    rot = subprocess.run(
        [sys.executable, LOGTICK, "rotate"],
        capture_output=True, text=True, env=env_for(state_dir),
    )
    if rot.returncode != 0:
        fail(f"B: rotate exit {rot.returncode}; err={rot.stderr!r}")
    else:
        if os.path.isfile(os.path.join(state_dir, "auto-evolve.log.1")):
            ok("B: rotation moved .log → .log.1")
        else:
            fail("B: rotation did not create .log.1")
        # Force several more rotations; at most 3 rotated files (≤ 4 total).
        for _ in range(5):
            with open(log, "w") as f:
                f.write("y" * (5 * 1024 * 1024 + 10) + "\n")
            subprocess.run(
                [sys.executable, LOGTICK, "rotate"],
                capture_output=True, text=True, env=env_for(state_dir),
            )
        rotated = [fn for fn in os.listdir(state_dir)
                   if fn.startswith("auto-evolve.log")]
        if len(rotated) <= 4:
            ok(f"B: at most 4 log files kept (got {len(rotated)}: {rotated})")
        else:
            fail(f"B: too many log files ({len(rotated)}): {rotated}")
        if "auto-evolve.log.4" not in rotated:
            ok("B: no .log.4 (oldest dropped)")
        else:
            fail("B: .log.4 exists — rotation kept too many")

# --- C: log off → zero file growth ------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    os.makedirs(state_dir, exist_ok=True)
    run_config(state_dir, "off")
    for t in range(20):
        write_one_tick(state_dir, t)
    n = len(log_lines(state_dir))
    if n == 0:
        ok("C: enable flag off → zero file growth")
    else:
        fail(f"C: log off but {n} lines were written")

# --- D: each emitted line < 2 KB --------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    os.makedirs(state_dir, exist_ok=True)
    run_config(state_dir, "level", "debug")
    big_blockers = ",".join(f"blocker-{i}-{'z' * 40}" for i in range(200))
    big_queue = ",".join(str(i) for i in range(2000))
    emit(state_dir, "tick-end", tick=1, session_id="s1",
         phase_reached="6", phase_result="aborted",
         queue_len=2000, queue_head=big_queue, blockers=big_blockers,
         in_flight=big_queue, merged_this_tick=big_queue,
         next_action="abort")
    lines = log_lines(state_dir)
    if not lines:
        fail("D: no line emitted for the oversized record")
    else:
        too_big = [ln for ln in lines if len(ln.encode("utf-8")) >= 2048]
        if not too_big:
            ok("D: every emitted line is < 2 KB (oversized payload truncated)")
        else:
            fail(f"D: {len(too_big)} line(s) ≥ 2 KB "
                 f"(max {max(len(l.encode('utf-8')) for l in lines)} bytes)")

# --- G: record carries minimum spec keys ------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    os.makedirs(state_dir, exist_ok=True)
    run_config(state_dir, "level", "normal")
    emit(state_dir, "tick-end", tick=7, session_id="s9",
         phase_reached="11", phase_result="ok", queue_len=1,
         queue_head="42", in_flight="42", merged_this_tick="100",
         blockers="", next_action="idle")
    lines = log_lines(state_dir)
    REQUIRED = ("ts", "tick", "session_id", "phase_reached", "phase_result",
                "in_flight", "queue_head", "queue_len", "merged_this_tick",
                "blockers", "next_action")
    if not lines:
        fail("G: no record emitted")
    else:
        rec = json.loads(lines[-1])
        missing = [k for k in REQUIRED if k not in rec]
        if not missing:
            ok("G: record carries all minimum spec keys")
        else:
            fail(f"G: record missing keys: {missing!r}")

# --- E: log-path.py prints the resolved path --------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    proc = subprocess.run(
        [sys.executable, LOGPATH], capture_output=True, text=True,
        env=env_for(state_dir),
    )
    expected = os.path.abspath(os.path.join(state_dir, "auto-evolve.log"))
    out = proc.stdout.strip()
    if proc.returncode == 0 and out == expected:
        ok("E: log-path.py prints the resolved auto-evolve.log path")
    else:
        fail(f"E: log-path.py exit {proc.returncode}; out={out!r} "
             f"expected {expected!r}")

# --- F: --help smoke for both scripts ---------------------------------
for label, script in (("log-tick.py", LOGTICK), ("log-path.py", LOGPATH)):
    proc = subprocess.run(
        [sys.executable, script, "--help"], capture_output=True, text=True,
    )
    blob = (proc.stdout + proc.stderr).lower()
    if proc.returncode == 0 and "usage" in blob:
        ok(f"F: {label} --help exits 0 with recognizable usage")
    else:
        fail(f"F: {label} --help exit {proc.returncode}; out={proc.stdout!r}")

sys.exit(FAIL)
