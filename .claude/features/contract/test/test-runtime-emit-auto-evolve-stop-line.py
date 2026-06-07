#!/usr/bin/env python3
"""test-runtime-emit-auto-evolve-stop-line.py — exercises
emit_auto_evolve_stop_line per Inv 55. Returns [] only when
.rabbit-auto-evolve-active is absent (the marker gates the whole composite
surface). When active, returns exactly ONE entry: a state marker (strict
priority aborted > restart-needed > stop-requested > running) wins when
present; otherwise the fall-through distinguishes the never-started window
(no .rabbit/auto-evolve-state.json -> restart-pending line, #793) from the
started-and-idle steady state (state file present -> idle line).
"""

import datetime
import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import emit_auto_evolve_stop_line  # noqa: E402

FAIL = 0

# Inv 67: the idle-line next-tick ETA is now zone-labelled. With no
# `display-timezone` configurable declared in these temp repos the resolver
# returns the local zone; a NAIVE injected `now` keeps its wall-clock value and
# gains the local zone label. We compute it here and suffix the expected
# "next tick HH:MM" strings so the boundary+offset arithmetic is unchanged,
# only labelled.
_LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo


def _eta_label(naive_hhmm):
    h, m = (int(x) for x in naive_hhmm.split(":"))
    dt = datetime.datetime(2026, 1, 1, h, m).replace(tzinfo=_LOCAL_TZ)
    return dt.strftime("%H:%M %Z")


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def touch(root, name):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w") as f:
        f.write("")


def write_state_file(root):
    """Create .rabbit/auto-evolve-state.json (loop started at least once)."""
    rabbit_dir = os.path.join(root, ".rabbit")
    os.makedirs(rabbit_dir, exist_ok=True)
    with open(os.path.join(rabbit_dir, "auto-evolve-state.json"), "w") as f:
        f.write("{}")


def write_cadence(root, cron):
    """Write repo-root .claude/scheduled_tasks.json with a heartbeat task."""
    claude_dir = os.path.join(root, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    payload = {"tasks": [{"id": "abc", "cron": cron,
                          "prompt": "/rabbit-auto-evolve tick",
                          "recurring": True}]}
    with open(os.path.join(claude_dir, "scheduled_tasks.json"), "w") as f:
        json.dump(payload, f)


def write_jitter(root, observed):
    """Write the rabbit-auto-evolve-owned jitter artifact (the offset contract
    READS to render the exact-time next-tick ETA)."""
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


def write_raw_cadence(root, raw):
    """Write a raw (possibly malformed) scheduled_tasks.json body."""
    claude_dir = os.path.join(root, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    with open(os.path.join(claude_dir, "scheduled_tasks.json"), "w") as f:
        f.write(raw)


ABORTED = ("auto-evolve loop aborted — see .rabbit/auto-evolve-state.json",
           "⛔", "red")
RESTART = ("auto-evolve loop awaiting restart", "⏸", "yellow")
STOP_REQ = ("auto-evolve loop stop requested — will exit on next tick",
            "⏸", "yellow")
RUNNING = ("auto-evolve loop running", "🔁", "green")
ACTIVE_IDLE = ("auto-evolve loop active — idle between ticks", "🔁", "green")
RESTART_PENDING = (
    "auto-evolve configured — restart Claude Code, then run /rabbit-auto-evolve start",
    "⏸", "yellow")


def assert_one(r, expected, label):
    text, icon, color = expected
    if len(r) != 1:
        fail(f"{label}: expected 1 entry, got {r!r}")
        return
    e = r[0]
    if e["type"] != "print" or e["text"] != text \
            or e["icon"] != icon or e["color"] != color:
        fail(f"{label}: entry wrong: {e!r} (expected text={text!r} icon={icon!r} color={color!r})")
        return
    ok(f"{label}: emitted {text!r}")


# A: no active marker -> []
with tempfile.TemporaryDirectory() as td:
    r = emit_auto_evolve_stop_line(repo_root=td)
    if r == []:
        ok("A: active marker absent returns []")
    else:
        fail(f"A: expected [], got {r!r}")

# B: active + aborted -> aborted entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ABORTED, "B")

# C: active + restart-needed -> restart entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-restart-needed")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RESTART, "C")

# D: active + stop-requested -> stop-requested entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-stop-requested")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, STOP_REQ, "D")

# E: active + running -> running entry
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RUNNING, "E")

# F: active only, NO state file (never started, post-on/pre-start window, #793)
#    -> exactly one restart-pending entry (NOT the idle line)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RESTART_PENDING, "F")

# F2: active + state file present (loop started at least once), no state markers
#     -> the steady active/idle entry (unchanged)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ACTIVE_IDLE, "F2")

# G (precedence): active + aborted + running -> aborted wins
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ABORTED, "G")

# H (precedence): active + restart-needed + stop-requested + running -> restart wins
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-restart-needed")
    touch(td, ".rabbit-auto-evolve-stop-requested")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RESTART, "H")

# I (precedence): active + stop-requested + running -> stop-requested wins
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-stop-requested")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, STOP_REQ, "I")

# J: active marker absent but other state markers present -> still []
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-running")
    touch(td, ".rabbit-auto-evolve-aborted")
    r = emit_auto_evolve_stop_line(repo_root=td)
    if r == []:
        ok("J: active absent gates whole surface, returns [] regardless of state markers")
    else:
        fail(f"J: expected [], got {r!r}")

# K: a state marker wins over the restart-pending fall-through even when the
#    state file is ABSENT (never-started window): active + running + no state
#    file -> running (state markers take strict priority over fall-through)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, RUNNING, "K")

# L: a state marker wins regardless of state file PRESENCE too: active +
#    aborted + state file present -> aborted
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    touch(td, ".rabbit-auto-evolve-aborted")
    write_state_file(td)
    r = emit_auto_evolve_stop_line(repo_root=td)
    assert_one(r, ABORTED, "L")

# ---- idle-line next-tick ETA (exact-time, boundary + jitter offset) ----
# The idle line carries a single bare EXACT-TIME form
# "next tick HH:MM" — HH:MM is the next cron fire at/after now PLUS the
# deterministic CronCreate per-job jitter offset (Inv 56), read from
# .rabbit/auto-evolve-tick-jitter.json (cold-start bound when absent). No ≥,
# no range, no qualifier. This mirrors the rabbit-auto-evolve banner-status.py
# "next tick HH:MM" form byte-for-byte so the SessionStart banner and the Stop
# line read consistently.
NOW = datetime.datetime(2026, 6, 4, 14, 5, 0)  # fixed injected now


def assert_text(r, expected_text, label):
    if len(r) != 1:
        fail(f"{label}: expected 1 entry, got {r!r}")
        return
    e = r[0]
    if e.get("text") != expected_text:
        fail(f"{label}: text wrong: {e.get('text')!r} (expected {expected_text!r})")
        return
    ok(f"{label}: emitted {expected_text!r}")


# M: idle + cadence + jitter artifact present -> idle line carries the exact
#    boundary+offset ETA. now=14:05, 13,43 -> boundary 14:13, +13 -> 14:26.
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    write_cadence(td, "13,43 * * * *")
    write_jitter(td, 13)
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    assert_text(r, f"auto-evolve loop active — idle, next tick {_eta_label('14:26')}", "M")
    # icon/color unchanged on the ETA idle line
    if r and (r[0].get("icon") != "🔁" or r[0].get("color") != "green"):
        fail(f"M: idle ETA line icon/color changed: {r[0]!r}")
    else:
        ok("M: idle ETA line keeps icon 🔁 / color green")

# N: idle + cadence absent -> bare idle line (graceful)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    assert_one(r, ACTIVE_IDLE, "N")

# O: idle + cadence unparseable JSON -> bare idle line (graceful)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    write_raw_cadence(td, "{not json")
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    assert_one(r, ACTIVE_IDLE, "O")

# P: idle + cadence with no rabbit-auto-evolve task -> bare idle line
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    write_raw_cadence(td, json.dumps(
        {"tasks": [{"id": "x", "cron": "0 * * * *", "prompt": "/something-else"}]}))
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    assert_one(r, ACTIVE_IDLE, "P")

# Q: cadence present must NOT leak ETA into the running state-marker line
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    write_cadence(td, "13,43 * * * *")
    touch(td, ".rabbit-auto-evolve-running")
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    assert_one(r, RUNNING, "Q")

# R: cadence present must NOT leak ETA into the restart-pending line
#    (active, no state markers, NO state file, cadence present)
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_cadence(td, "13,43 * * * *")
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    assert_one(r, RESTART_PENDING, "R")

# S: cadence present + active marker absent -> still [] (no ETA, gate holds)
with tempfile.TemporaryDirectory() as td:
    write_cadence(td, "13,43 * * * *")
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    if r == []:
        ok("S: active absent gates surface even with cadence present")
    else:
        fail(f"S: expected [], got {r!r}")

# T: minute already exactly on a fire boundary at now -> next is the LATER slot
#    now=14:13 with 13,43 -> boundary 14:43, +13 -> 14:56
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    write_cadence(td, "13,43 * * * *")
    write_jitter(td, 13)
    r = emit_auto_evolve_stop_line(
        repo_root=td, now=datetime.datetime(2026, 6, 4, 14, 13, 0))
    assert_text(r, f"auto-evolve loop active — idle, next tick {_eta_label('14:56')}", "T")

# U: wrap to next hour: now=14:50 with 13,43 -> boundary 15:13, +13 -> 15:26
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    write_cadence(td, "13,43 * * * *")
    write_jitter(td, 13)
    r = emit_auto_evolve_stop_line(
        repo_root=td, now=datetime.datetime(2026, 6, 4, 14, 50, 0))
    assert_text(r, f"auto-evolve loop active — idle, next tick {_eta_label('15:26')}", "U")

# V: cadence present, jitter artifact ABSENT -> cold-start fallback offset.
#    now=14:05, 13,43 -> boundary 14:13, period 30 -> +min(15,ceil(3))=+3 -> 14:16
with tempfile.TemporaryDirectory() as td:
    touch(td, ".rabbit-auto-evolve-active")
    write_state_file(td)
    write_cadence(td, "13,43 * * * *")
    r = emit_auto_evolve_stop_line(repo_root=td, now=NOW)
    assert_text(r, f"auto-evolve loop active — idle, next tick {_eta_label('14:16')}", "V")

if FAIL:
    print("test-runtime-emit-auto-evolve-stop-line: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-emit-auto-evolve-stop-line: all checks passed.")
