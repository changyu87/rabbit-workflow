#!/usr/bin/env python3
"""test-schedule-decision.py — e2e tests for scripts/schedule-decision.py
(Inv 33 / D1, issue #521).

`schedule-decision.py` determines open-work presence AUTHORITATIVELY by
invoking the EXISTING `fetch-queue.py` and counting items, reads the
scheduler mechanism from `detect-scheduler.py`, logs the decision via
`tick-log.py`, and emits JSON:
  - queue non-empty -> {"decision":"immediate-refire", ...}
  - queue empty     -> {"decision":"idle", "detail":"rely on heartbeat"}

The test injects a fake `fetch-queue.py` via the
`RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD` override (a tiny program emitting a
canned JSON array) so no `gh` call is made, and a `RABBIT_CRONTAB_CMD`
crontab shim so scheduler detection is deterministic.

Scenarios:
  A) non-empty queue + usable crontab    -> immediate-refire, scheduler crontab
  B) non-empty queue + restricted crontab-> immediate-refire, scheduler
     croncreate, with a croncreate one-shot param block
  C) empty queue                          -> idle
  D) the decision is logged to .rabbit/tick.log
  E) --help smoke
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
DECIDE = os.path.join(SCRIPTS, "schedule-decision.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_fetch_shim(dirpath, json_array):
    shim = os.path.join(dirpath, "fetch-queue-shim.py")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys
            sys.stdout.write({json_array!r})
            sys.exit(0)
            """))
    os.chmod(shim, 0o755)
    return shim


def make_crontab_shim(dirpath, restricted):
    shim = os.path.join(dirpath, "crontab")
    if restricted:
        body = (
            'import sys\n'
            'sys.stderr.write("You (t) are not allowed to use this '
            'program (crontab)\\n")\nsys.exit(1)\n'
        )
    else:
        body = 'import sys\nsys.exit(0)\n'
    with open(shim, "w") as f:
        f.write(f"#!{sys.executable}\n" + body)
    os.chmod(shim, 0o755)
    return shim


def run(d, queue_json, restricted=False):
    fetch = make_fetch_shim(d, queue_json)
    cron = make_crontab_shim(d, restricted)
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD"] = fetch
    env["RABBIT_CRONTAB_CMD"] = cron
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(d, ".rabbit")
    return subprocess.run(
        [sys.executable, DECIDE], capture_output=True, text=True, env=env,
    )


def parsed(proc):
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


NONEMPTY = '[{"number": 1, "title": "x", "labels": []}]'
EMPTY = "[]"

# A — non-empty + usable crontab
with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=False)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("decision") == "immediate-refire" \
            and j.get("scheduler") == "crontab":
        ok("A: non-empty + crontab -> immediate-refire, scheduler crontab")
    else:
        fail(f"A: out={proc.stdout!r} err={proc.stderr!r}")
    if j and j.get("prompt") == "/rabbit-auto-evolve start":
        ok("A: refire prompt is /rabbit-auto-evolve start")
    else:
        fail(f"A: wrong/absent prompt: {j!r}")

# B — non-empty + restricted crontab
with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=True)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("decision") == "immediate-refire" \
            and j.get("scheduler") == "croncreate":
        ok("B: non-empty + restricted -> immediate-refire, scheduler croncreate")
    else:
        fail(f"B: out={proc.stdout!r} err={proc.stderr!r}")
    cc = (j or {}).get("croncreate")
    if isinstance(cc, dict) and cc.get("prompt") == "/rabbit-auto-evolve start" \
            and cc.get("durable") is False and cc.get("recurring") is False \
            and cc.get("cron"):
        ok("B: croncreate one-shot block carries cron/prompt/durable=false")
    else:
        fail(f"B: croncreate block malformed: {cc!r}")

# C — empty queue
with tempfile.TemporaryDirectory() as d:
    proc = run(d, EMPTY, restricted=False)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("decision") == "idle":
        ok("C: empty queue -> idle")
    else:
        fail(f"C: out={proc.stdout!r} err={proc.stderr!r}")

# D — decision logged
with tempfile.TemporaryDirectory() as d:
    run(d, EMPTY, restricted=False)
    log = os.path.join(d, ".rabbit", "tick.log")
    if os.path.isfile(log) and "idle" in open(log).read().lower():
        ok("D: the idle decision was logged to .rabbit/tick.log")
    else:
        fail("D: decision not logged to .rabbit/tick.log")

# E — --help smoke
proc = subprocess.run(
    [sys.executable, DECIDE, "--help"], capture_output=True, text=True,
)
if proc.returncode == 0 and "refire" in (proc.stdout + proc.stderr).lower():
    ok("E: --help exits 0 with recognizable usage")
else:
    fail(f"E: --help exit {proc.returncode}; out={proc.stdout!r}")

sys.exit(FAIL)
