#!/usr/bin/env python3
"""test-runtime-next-tick-eta.py — exercises the contract.lib.runtime
_auto_evolve_next_tick_eta helper. The helper reads repo-root
.claude/scheduled_tasks.json, locates the rabbit-auto-evolve heartbeat task,
parses its 5-field cron minute/hour fields, and renders the next wall-clock
fire at/after an INJECTED `now` as a jitter-inclusive RANGE
"~HH:MM–HH:MM (scheduler jitter)" (or None on any
absent/unreadable/unparseable/no-match condition). The range's LOW bound is
the scheduled fire minute; the HIGH bound is that fire plus the bounded
CronCreate scheduler jitter (up to 10% of the cadence period, capped at 15
min, floored at 1 min), so the displayed window is honest and never reads
EARLY. Determinism: `now` is always injected; the helper never reads the real
clock. This mirrors the rabbit-auto-evolve banner-status.py range form so the
SessionStart banner and the Stop line read consistently.
"""

import datetime
import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import _auto_evolve_next_tick_eta  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_cadence(root, cron, prompt="/rabbit-auto-evolve tick"):
    claude_dir = os.path.join(root, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    payload = {"tasks": [{"id": "abc", "cron": cron, "prompt": prompt}]}
    with open(os.path.join(claude_dir, "scheduled_tasks.json"), "w") as f:
        json.dump(payload, f)


def write_raw(root, raw):
    claude_dir = os.path.join(root, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    with open(os.path.join(claude_dir, "scheduled_tasks.json"), "w") as f:
        f.write(raw)


def check(cron, now, expected, label):
    with tempfile.TemporaryDirectory() as td:
        write_cadence(td, cron)
        got = _auto_evolve_next_tick_eta(td, now)
        if got == expected:
            ok(f"{label}: cron={cron!r} now={now.strftime('%H:%M')} -> {got!r}")
        else:
            fail(f"{label}: cron={cron!r} now={now.strftime('%H:%M')} -> {got!r} (expected {expected!r})")


D = datetime.datetime

# All expected values are the jitter-inclusive RANGE form
# "~HH:MM–HH:MM (scheduler jitter)" — LOW is the next scheduled fire at/after
# now, HIGH is LOW + the bounded scheduler jitter (max(1, min(15,
# ceil(period*0.10)))). Cadence periods below: 13,43 -> 30 min (jitter 3);
# */15 -> 15 min (jitter 2); * -> 1 min (jitter 1); single fixed -> 60 (jitter
# 6).

# minute list, next slot within the same hour: period 30 -> jitter 3
check("13,43 * * * *", D(2026, 6, 4, 14, 5), "~14:13–14:16 (scheduler jitter)", "list-before-first")
check("13,43 * * * *", D(2026, 6, 4, 14, 20), "~14:43–14:46 (scheduler jitter)", "list-between")
# on-boundary now -> strictly-later slot
check("13,43 * * * *", D(2026, 6, 4, 14, 13), "~14:43–14:46 (scheduler jitter)", "on-boundary")
# wrap to next hour
check("13,43 * * * *", D(2026, 6, 4, 14, 50), "~15:13–15:16 (scheduler jitter)", "wrap-next-hour")
# wrap across midnight
check("13,43 * * * *", D(2026, 6, 4, 23, 50), "~00:13–00:16 (scheduler jitter)", "wrap-midnight")
# upper bound itself wraps across the hour boundary (13,58 -> period 15 ->
# jitter 2; next fire 14:58 + 2 -> 15:00)
check("13,58 * * * *", D(2026, 6, 4, 14, 50), "~14:58–15:00 (scheduler jitter)", "upper-wrap-hour")
# step form */15 -> 0,15,30,45: period 15 -> jitter 2
check("*/15 * * * *", D(2026, 6, 4, 9, 7), "~09:15–09:17 (scheduler jitter)", "step-15")
check("*/15 * * * *", D(2026, 6, 4, 9, 46), "~10:00–10:02 (scheduler jitter)", "step-15-wrap")
# every minute: period 1 -> jitter 1
check("* * * * *", D(2026, 6, 4, 9, 7), "~09:08–09:09 (scheduler jitter)", "every-minute")
check("* * * * *", D(2026, 6, 4, 9, 59), "~10:00–10:01 (scheduler jitter)", "every-minute-wrap")
# single fixed minute: period 60 -> jitter 6
check("0 * * * *", D(2026, 6, 4, 9, 7), "~10:00–10:06 (scheduler jitter)", "single-minute")

# --- None fallbacks ---
with tempfile.TemporaryDirectory() as td:
    # absent file
    if _auto_evolve_next_tick_eta(td, D(2026, 6, 4, 14, 5)) is None:
        ok("absent-file -> None")
    else:
        fail("absent-file: expected None")

with tempfile.TemporaryDirectory() as td:
    write_raw(td, "{not json")
    if _auto_evolve_next_tick_eta(td, D(2026, 6, 4, 14, 5)) is None:
        ok("unparseable-json -> None")
    else:
        fail("unparseable-json: expected None")

with tempfile.TemporaryDirectory() as td:
    write_cadence(td, "13,43 * * * *", prompt="/something-else")
    if _auto_evolve_next_tick_eta(td, D(2026, 6, 4, 14, 5)) is None:
        ok("no-matching-task -> None")
    else:
        fail("no-matching-task: expected None")

with tempfile.TemporaryDirectory() as td:
    write_raw(td, json.dumps({"tasks": []}))
    if _auto_evolve_next_tick_eta(td, D(2026, 6, 4, 14, 5)) is None:
        ok("empty-tasks -> None")
    else:
        fail("empty-tasks: expected None")

with tempfile.TemporaryDirectory() as td:
    write_cadence(td, "not a cron")
    if _auto_evolve_next_tick_eta(td, D(2026, 6, 4, 14, 5)) is None:
        ok("unparseable-cron -> None")
    else:
        fail("unparseable-cron: expected None")

if FAIL:
    print("test-runtime-next-tick-eta: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-next-tick-eta: all checks passed.")
