#!/usr/bin/env python3
"""test-runtime-next-tick-eta.py — exercises the contract.lib.runtime
_auto_evolve_next_tick_eta helper. The helper reads repo-root
.claude/scheduled_tasks.json, locates the rabbit-auto-evolve heartbeat task,
parses its 5-field cron minute/hour fields, and renders the EXACT next
wall-clock fire at/after an INJECTED `now` as the idle-gated boundary form
"≥ HH:MM (fires when the session is next idle)" (or None on any
absent/unreadable/unparseable/no-match condition). The displayed HH:MM is the
deterministic next cron boundary — cron matches its exact minute, so there is
no "scheduler jitter". The next-tick overshoot is the idle-gated DELIVERY wait
(the CronCreate fallback fires a scheduled prompt only while the REPL is idle),
so the tick fires AT or AFTER the boundary, never before — named honestly by
the `≥` and the "(fires when the session is next idle)" qualifier.
Determinism: `now` is always injected; the helper never reads the real clock.
This mirrors the rabbit-auto-evolve banner-status.py boundary form byte-for-byte
so the SessionStart banner and the Stop line read consistently.
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

# All expected values are the idle-gated boundary form
# "≥ HH:MM (fires when the session is next idle)" — HH:MM is the EXACT next
# cron fire at/after now (deterministic; no jitter range).
Q = " (fires when the session is next idle)"

# minute list, next slot within the same hour
check("13,43 * * * *", D(2026, 6, 4, 14, 5), "≥ 14:13" + Q, "list-before-first")
check("13,43 * * * *", D(2026, 6, 4, 14, 20), "≥ 14:43" + Q, "list-between")
# on-boundary now -> strictly-later slot
check("13,43 * * * *", D(2026, 6, 4, 14, 13), "≥ 14:43" + Q, "on-boundary")
# wrap to next hour
check("13,43 * * * *", D(2026, 6, 4, 14, 50), "≥ 15:13" + Q, "wrap-next-hour")
# wrap across midnight
check("13,43 * * * *", D(2026, 6, 4, 23, 50), "≥ 00:13" + Q, "wrap-midnight")
# late-hour fire minute, next slot same hour
check("13,58 * * * *", D(2026, 6, 4, 14, 50), "≥ 14:58" + Q, "late-minute-same-hour")
# step form */15 -> 0,15,30,45
check("*/15 * * * *", D(2026, 6, 4, 9, 7), "≥ 09:15" + Q, "step-15")
check("*/15 * * * *", D(2026, 6, 4, 9, 46), "≥ 10:00" + Q, "step-15-wrap")
# every minute
check("* * * * *", D(2026, 6, 4, 9, 7), "≥ 09:08" + Q, "every-minute")
check("* * * * *", D(2026, 6, 4, 9, 59), "≥ 10:00" + Q, "every-minute-wrap")
# single fixed minute
check("0 * * * *", D(2026, 6, 4, 9, 7), "≥ 10:00" + Q, "single-minute")

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
