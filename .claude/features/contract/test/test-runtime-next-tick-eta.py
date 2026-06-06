#!/usr/bin/env python3
"""test-runtime-next-tick-eta.py — exercises the contract.lib.runtime
_auto_evolve_next_tick_eta helper. The helper reads repo-root
.claude/scheduled_tasks.json, locates the rabbit-auto-evolve heartbeat task,
parses its cron minute field, and renders the next wall-clock fire at/after an
INJECTED `now` as a SINGLE bare EXACT-TIME `HH:MM` string — the next cron
boundary PLUS the deterministic CronCreate per-job jitter offset (Inv 56). It
returns None on any absent/unreadable/unparseable/no-match condition (caller
degrades to the bare idle line; no fabricated ETA).

CronCreate adds a deterministic per-job jitter to recurring tasks: they fire
late by a stable per-job offset (observed CONSTANT +13 min on the 30-min 13,43
heartbeat, on an IDLE session). The offset is READ from the
rabbit-auto-evolve-owned artifact .rabbit/auto-evolve-tick-jitter.json
(`observed_jitter_minutes`); when that artifact is absent the offset falls back
to the documented cold-start bound `min(15, ceil(period_minutes * 0.10))`,
exactly as rabbit-auto-evolve's banner-status.py does — so the SessionStart
banner and the Stop line render the same `next tick HH:MM` value byte-for-byte.

There is NO `≥`, NO `~`, NO range, and NO qualifier — the rejected mental
models ("scheduler jitter" range, "fires when the session is next idle"
idle-gating) are purged. A source-grep guard at the bottom asserts none of
those phrases survive in runtime.py.

Determinism: `now` is always injected; the helper never reads the real clock.
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


def write_jitter(root, observed):
    """Write the rabbit-auto-evolve-owned jitter artifact with a fixed
    observed_jitter_minutes value (the offset contract READS)."""
    rabbit_dir = os.path.join(root, ".rabbit")
    os.makedirs(rabbit_dir, exist_ok=True)
    payload = {
        "schema_version": 1,
        "observed_jitter_minutes": observed,
        "period_minutes": 30,
        "sample_count": 8,
        "cold_start": False,
        "computed_at": "2026-06-04T14:00:00",
        "owner": "rabbit-workflow team (rabbit-auto-evolve)",
        "deprecation_criterion": "when CronCreate exposes a jitter-free schedule",
    }
    with open(os.path.join(rabbit_dir, "auto-evolve-tick-jitter.json"), "w") as f:
        json.dump(payload, f)


def write_raw(root, raw):
    claude_dir = os.path.join(root, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    with open(os.path.join(claude_dir, "scheduled_tasks.json"), "w") as f:
        f.write(raw)


def check_empirical(cron, now, jitter, expected, label):
    """Cadence + jitter artifact present -> boundary + observed_jitter_minutes."""
    with tempfile.TemporaryDirectory() as td:
        write_cadence(td, cron)
        write_jitter(td, jitter)
        got = _auto_evolve_next_tick_eta(td, now)
        if got == expected:
            ok(f"{label}: cron={cron!r} now={now.strftime('%H:%M')} +{jitter} -> {got!r}")
        else:
            fail(f"{label}: cron={cron!r} now={now.strftime('%H:%M')} +{jitter} -> {got!r} (expected {expected!r})")


def check_coldstart(cron, now, expected, label):
    """Cadence present, jitter artifact ABSENT -> boundary + cold-start bound."""
    with tempfile.TemporaryDirectory() as td:
        write_cadence(td, cron)
        got = _auto_evolve_next_tick_eta(td, now)
        if got == expected:
            ok(f"{label}: cron={cron!r} now={now.strftime('%H:%M')} cold-start -> {got!r}")
        else:
            fail(f"{label}: cron={cron!r} now={now.strftime('%H:%M')} cold-start -> {got!r} (expected {expected!r})")


D = datetime.datetime

# --- empirical offset (observed_jitter_minutes from the artifact) ---
# The canonical #881 case: jitter=13, 13,43 cadence, now=14:40 -> next boundary
# 14:43, +13 -> "14:56". A SINGLE bare HH:MM, no qualifier.
check_empirical("13,43 * * * *", D(2026, 6, 4, 14, 40), 13, "14:56", "canonical-+13")
# next slot within the same hour, +13
check_empirical("13,43 * * * *", D(2026, 6, 4, 14, 5), 13, "14:26", "list-before-first")
check_empirical("13,43 * * * *", D(2026, 6, 4, 14, 20), 13, "14:56", "list-between")
# on-boundary now -> strictly-later slot, +13
check_empirical("13,43 * * * *", D(2026, 6, 4, 14, 13), 13, "14:56", "on-boundary")
# offset can push the displayed time across the hour
check_empirical("13,43 * * * *", D(2026, 6, 4, 14, 50), 13, "15:26", "wrap-next-hour")
# offset can push across midnight
check_empirical("13,43 * * * *", D(2026, 6, 4, 23, 50), 13, "00:26", "wrap-midnight")
# zero offset -> bare boundary
check_empirical("13,43 * * * *", D(2026, 6, 4, 14, 20), 0, "14:43", "zero-offset")
# different offset value flows through verbatim
check_empirical("13,43 * * * *", D(2026, 6, 4, 14, 20), 7, "14:50", "offset-7")

# --- cold-start fallback (no jitter artifact) ---
# period for 13,43 is 30 -> min(15, ceil(30*0.10)) = min(15, 3) = 3
check_coldstart("13,43 * * * *", D(2026, 6, 4, 14, 20), "14:46", "coldstart-30min-+3")
# */15 -> period 15 -> min(15, ceil(15*0.10)) = min(15, 2) = 2
check_coldstart("*/15 * * * *", D(2026, 6, 4, 9, 7), "09:17", "coldstart-15min-+2")
# single fixed minute -> period 60 -> min(15, ceil(60*0.10)) = min(15, 6) = 6
check_coldstart("0 * * * *", D(2026, 6, 4, 9, 7), "10:06", "coldstart-60min-+6")
# every-minute -> period 1 -> min(15, ceil(1*0.10)) = min(15, 1) = 1
check_coldstart("* * * * *", D(2026, 6, 4, 9, 7), "09:09", "coldstart-1min-+1")

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

# Unusable observed_jitter_minutes (wrong type / negative) falls back to
# cold-start, never crashes.
with tempfile.TemporaryDirectory() as td:
    write_cadence(td, "13,43 * * * *")
    rabbit_dir = os.path.join(td, ".rabbit")
    os.makedirs(rabbit_dir, exist_ok=True)
    with open(os.path.join(rabbit_dir, "auto-evolve-tick-jitter.json"), "w") as f:
        json.dump({"observed_jitter_minutes": -5}, f)
    got = _auto_evolve_next_tick_eta(td, D(2026, 6, 4, 14, 20))
    if got == "14:46":  # falls back to cold-start +3
        ok("negative-offset -> cold-start fallback")
    else:
        fail(f"negative-offset: expected cold-start 14:46, got {got!r}")

# --- source-grep guard: the rejected mental models must be PURGED ---
RUNTIME_PATH = os.path.join(FEATURE_DIR, "lib", "runtime.py")
with open(RUNTIME_PATH, encoding="utf-8") as f:
    runtime_src = f.read()

BANNED = [
    "≥",  # the ≥ lower-bound framing
    "scheduler jitter",
    "fires when the session is next idle",
    "idle-gat",  # idle-gated / idle-gating delivery-wait story
]
for phrase in BANNED:
    if phrase in runtime_src:
        fail(f"purge-guard: rejected phrase {phrase!r} still present in runtime.py")
    else:
        ok(f"purge-guard: {phrase!r} absent from runtime.py")

if FAIL:
    print("test-runtime-next-tick-eta: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-next-tick-eta: all checks passed.")
