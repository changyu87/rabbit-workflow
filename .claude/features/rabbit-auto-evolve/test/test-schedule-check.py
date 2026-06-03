#!/usr/bin/env python3
"""test-schedule-check.py — rabbit-auto-evolve Inv 29 (issue #409).

Exercises scripts/schedule-check.py, the runtime validator for the
ScheduleWakeup parameters the tick's phase 11 (`schedule`) emits. The
script cannot test the harness `ScheduleWakeup` call itself (it is a
Claude Code feature, not a Python function); it validates the LOGIC that
determines the call's parameters — the delay range, the non-empty
re-invoke prompt, and the non-empty reason — BEFORE the call is emitted.

Contract under test (CLI):
  python3 scripts/schedule-check.py \
    --delay-seconds N --prompt "<str>" --reason "<str>"

  - exit 0 + emits a JSON object {"ok": true, "delay_seconds": N,
    "prompt": "...", "reason": "..."} when all params are valid;
  - exit non-zero + {"ok": false, "errors": [...]} on any violation;
  - --help exits 0 with recognizable usage text.

Validity rules (issue #409):
  - 60 <= delay_seconds <= 3600 (the silent-stop bug shipped a delay
    outside this band — 0 is rejected/ignored by the harness, and an
    over-long delay looks like a hang);
  - prompt is non-empty AND re-invokes the tick (contains the literal
    substring `/rabbit-auto-evolve tick`);
  - reason is non-empty.
"""

import json
import os
import subprocess
import sys

SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "scripts",
    "schedule-check.py",
)

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run(args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
    )


VALID_PROMPT = "/rabbit-auto-evolve tick"
VALID_REASON = "chain the next auto-evolve tick"


def valid_args(delay=900, prompt=VALID_PROMPT, reason=VALID_REASON):
    return [
        "--delay-seconds",
        str(delay),
        "--prompt",
        prompt,
        "--reason",
        reason,
    ]


# --- Smoke: --help -------------------------------------------------------
r = run(["--help"])
if r.returncode == 0 and "schedule" in (r.stdout + r.stderr).lower():
    ok("--help exits 0 with recognizable usage text")
else:
    fail(f"--help smoke failed: rc={r.returncode} out={r.stdout!r} err={r.stderr!r}")


# --- Happy path: all params valid ---------------------------------------
r = run(valid_args())
if r.returncode == 0:
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        obj = None
        fail(f"happy path: stdout not JSON ({e}): {r.stdout!r}")
    if obj is not None:
        if obj.get("ok") is True and obj.get("delay_seconds") == 900:
            ok("valid params → exit 0 + ok:true")
        else:
            fail(f"happy path: unexpected JSON {obj!r}")
else:
    fail(f"happy path: expected exit 0, got {r.returncode}; err={r.stderr!r}")


# --- Delay too small (0 — the harness-rejected value) -------------------
r = run(valid_args(delay=0))
if r.returncode != 0:
    ok("delay_seconds=0 → non-zero exit")
else:
    fail("delay_seconds=0 must be rejected (non-zero exit)")

# --- Delay below the 60s floor ------------------------------------------
r = run(valid_args(delay=59))
if r.returncode != 0:
    ok("delay_seconds=59 (below floor) → non-zero exit")
else:
    fail("delay_seconds=59 must be rejected (< 60)")

# --- Delay above the 3600s ceiling --------------------------------------
r = run(valid_args(delay=3601))
if r.returncode != 0:
    ok("delay_seconds=3601 (above ceiling) → non-zero exit")
else:
    fail("delay_seconds=3601 must be rejected (> 3600)")

# --- Boundary values are inclusive --------------------------------------
for boundary in (60, 3600):
    r = run(valid_args(delay=boundary))
    if r.returncode == 0:
        ok(f"delay_seconds={boundary} (inclusive boundary) → exit 0")
    else:
        fail(f"delay_seconds={boundary} must be accepted (inclusive boundary)")

# --- Empty prompt --------------------------------------------------------
r = run(valid_args(prompt=""))
if r.returncode != 0:
    ok("empty prompt → non-zero exit")
else:
    fail("empty prompt must be rejected")

# --- Prompt that does NOT re-invoke the tick ----------------------------
r = run(valid_args(prompt="just wake up please"))
if r.returncode != 0:
    ok("prompt without /rabbit-auto-evolve tick → non-zero exit")
else:
    fail("prompt that does not re-invoke the tick must be rejected")

# --- Empty reason --------------------------------------------------------
r = run(valid_args(reason=""))
if r.returncode != 0:
    ok("empty reason → non-zero exit")
else:
    fail("empty reason must be rejected")

# --- Error payload shape on a violation ---------------------------------
r = run(valid_args(delay=0))
try:
    obj = json.loads(r.stdout)
    if obj.get("ok") is False and isinstance(obj.get("errors"), list) and obj["errors"]:
        ok("violation → {ok:false, errors:[...]} payload")
    else:
        fail(f"violation payload malformed: {obj!r}")
except json.JSONDecodeError:
    fail(f"violation: stdout not JSON: {r.stdout!r}")

sys.exit(FAIL)
