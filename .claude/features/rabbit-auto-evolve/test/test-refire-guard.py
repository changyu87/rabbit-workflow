#!/usr/bin/env python3
"""test-refire-guard.py — e2e tests for scripts/refire-guard.py (Inv 65,
issue #1051).

Phase 12 `schedule-decision.py` emits `immediate-refire` when dispatchable
work remains; the SKILL.md asks the DISPATCHER (a Claude step) to `CronCreate`
the one-shot refire. That CronCreate is an irreducible Claude tool action, and
NOTHING verifies it happened. If the dispatcher ends the turn without creating
the one-shot, the loop silently stops self-continuing — the silent-stop failure
mode the Scheduling section claims to have eliminated.

`refire-guard.py` makes the dropped refire DETERMINISTICALLY OBSERVABLE. At the
NEXT tick start it reconciles the PRIOR tick's schedule decision (a breadcrumb
already written to `.rabbit/tick.log` by schedule-decision.py) against the
current state: if the last decision was `immediate-refire`, the dispatchable
plan is STILL non-empty, and more than a heartbeat-interval has elapsed since
that decision (so the refire clearly did NOT fire promptly — a prompt refire
would have entered a new tick and logged a fresh decision well within a
heartbeat), it emits a LOUD `tick.log` warning and sets `refire_owed: true` so
the dispatcher MUST act. CronCreate stays a Claude action; the guard DETECTS +
SURFACES the drop.

Scenarios:
  A) prior immediate-refire + plan still non-empty + > heartbeat elapsed ->
     refire_owed true, a LOUD warning appended to tick.log
  B) prior immediate-refire that FIRED promptly (a fresh decision is the last
     line, small elapsed) -> refire_owed false, no warning
  C) prior decision was `idle` -> refire_owed false (nothing was owed)
  D) prior immediate-refire but the plan is now EMPTY -> refire_owed false
     (the work was drained/blocked since; the heartbeat backstop is correct)
  E) empty / absent tick.log -> refire_owed false (no prior decision)
  F) the pure reconcile() predicate is unit-testable in isolation
  G) --help smoke
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
GUARD = os.path.join(SCRIPTS, "refire-guard.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _load_guard_module():
    spec = importlib.util.spec_from_file_location("refire_guard", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_log(state_dir, records):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "tick.log"), "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def read_log_lines(state_dir):
    path = os.path.join(state_dir, "tick.log")
    if not os.path.isfile(path):
        return []
    return [ln for ln in open(path).read().splitlines() if ln.strip()]


# An immediate-refire decision logged ~40 min ago — well past the default
# 30-min heartbeat interval, so a prompt refire would already have produced a
# newer tick.log decision. The absence of a newer decision means the refire was
# dropped.
STALE_REFIRE_TS = "2026-06-07T00:00:00Z"
# "now" the guard sees is injected via RABBIT_AUTO_EVOLVE_NOW. 40 min after the
# stale ts (past the heartbeat); 1 min after (inside the window).
NOW_40MIN = "2026-06-07T00:40:00Z"
NOW_1MIN = "2026-06-07T00:01:00Z"


def run_now(state_dir, plan_nonempty, now):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    env["RABBIT_AUTO_EVOLVE_NOW"] = now
    args = [sys.executable, GUARD,
            "--plan-nonempty" if plan_nonempty else "--plan-empty"]
    return subprocess.run(args, capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# A — dropped refire: prior immediate-refire + plan still non-empty + stale.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    write_log(state_dir, [
        {"ts": STALE_REFIRE_TS, "decision": "immediate-refire",
         "detail": "dispatchable work=2, scheduler=croncreate"},
    ])
    before = len(read_log_lines(state_dir))
    proc = run_now(state_dir, plan_nonempty=True, now=NOW_40MIN)
    if proc.returncode != 0:
        fail(f"A: guard exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("A: guard exited 0")
    try:
        res = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        res = {}
        fail(f"A: stdout not JSON: {proc.stdout!r}")
    if res.get("refire_owed") is True:
        ok("A: refire_owed true when a refire was decided but never fired")
    else:
        fail(f"A: refire_owed not true on a dropped refire: {res!r}")
    after_lines = read_log_lines(state_dir)
    if len(after_lines) > before:
        last = json.loads(after_lines[-1])
        blob = (last.get("decision", "") + " " + last.get("detail", "")).lower()
        if "refire" in blob and "owed" in blob:
            ok("A: a LOUD refire-owed warning was appended to tick.log")
        else:
            fail(f"A: appended line is not a refire-owed warning: {last!r}")
    else:
        fail("A: no warning line appended to tick.log on a dropped refire")


# ---------------------------------------------------------------------------
# B — refire fired promptly: the last decision is a FRESH refire (small
# elapsed) -> not owed, no warning.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    write_log(state_dir, [
        {"ts": STALE_REFIRE_TS, "decision": "immediate-refire",
         "detail": "dispatchable work=2, scheduler=croncreate"},
        # the refire fired: a new tick entered and logged a fresh decision.
        {"ts": NOW_1MIN, "decision": "immediate-refire",
         "detail": "dispatchable work=1, scheduler=croncreate"},
    ])
    before = len(read_log_lines(state_dir))
    proc = run_now(state_dir, plan_nonempty=True, now=NOW_40MIN)
    res = json.loads(proc.stdout)
    if res.get("refire_owed") is False:
        ok("B: refire_owed false when the last refire decision is fresh")
    else:
        fail(f"B: refire_owed not false on a promptly-fired refire: {res!r}")
    if len(read_log_lines(state_dir)) == before:
        ok("B: no warning appended when the refire fired promptly")
    else:
        fail("B: a warning was wrongly appended on a promptly-fired refire")


# ---------------------------------------------------------------------------
# C — prior decision was idle -> nothing owed.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    write_log(state_dir, [
        {"ts": STALE_REFIRE_TS, "decision": "idle: no dispatchable work",
         "detail": "selection_order empty"},
    ])
    proc = run_now(state_dir, plan_nonempty=True, now=NOW_40MIN)
    res = json.loads(proc.stdout)
    if res.get("refire_owed") is False:
        ok("C: refire_owed false when the prior decision was idle")
    else:
        fail(f"C: refire_owed not false on a prior idle decision: {res!r}")


# ---------------------------------------------------------------------------
# D — prior immediate-refire but the plan is now EMPTY -> not owed (the work
# drained/blocked since; the heartbeat backstop is the correct outcome).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")
    write_log(state_dir, [
        {"ts": STALE_REFIRE_TS, "decision": "immediate-refire",
         "detail": "dispatchable work=2, scheduler=croncreate"},
    ])
    before = len(read_log_lines(state_dir))
    proc = run_now(state_dir, plan_nonempty=False, now=NOW_40MIN)
    res = json.loads(proc.stdout)
    if res.get("refire_owed") is False:
        ok("D: refire_owed false when the dispatchable plan is now empty")
    else:
        fail(f"D: refire_owed not false with an empty plan: {res!r}")
    if len(read_log_lines(state_dir)) == before:
        ok("D: no warning appended when the plan is now empty")
    else:
        fail("D: a warning was wrongly appended with an empty plan")


# ---------------------------------------------------------------------------
# E — empty / absent tick.log -> not owed (no prior decision to reconcile).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    state_dir = os.path.join(d, ".rabbit")  # never created
    proc = run_now(state_dir, plan_nonempty=True, now=NOW_40MIN)
    if proc.returncode != 0:
        fail(f"E: guard exit {proc.returncode} on absent log; "
             f"stderr={proc.stderr!r}")
    res = json.loads(proc.stdout)
    if res.get("refire_owed") is False:
        ok("E: refire_owed false on an absent tick.log")
    else:
        fail(f"E: refire_owed not false on an absent tick.log: {res!r}")


# ---------------------------------------------------------------------------
# F — pure reconcile() predicate unit tests.
# ---------------------------------------------------------------------------
mod = _load_guard_module()
HEARTBEAT = 1800  # 30 min

# dropped: stale immediate-refire, plan non-empty, elapsed > heartbeat.
owed, _ = mod.reconcile(
    [{"ts": STALE_REFIRE_TS, "decision": "immediate-refire", "detail": ""}],
    plan_nonempty=True, now_iso=NOW_40MIN, heartbeat_secs=HEARTBEAT,
)
if owed is True:
    ok("F: reconcile() owed=True on a stale dropped refire")
else:
    fail(f"F: reconcile() owed not True on a dropped refire: {owed!r}")

# within the heartbeat window -> not yet owed (the refire may still fire).
owed, _ = mod.reconcile(
    [{"ts": STALE_REFIRE_TS, "decision": "immediate-refire", "detail": ""}],
    plan_nonempty=True, now_iso=NOW_1MIN, heartbeat_secs=HEARTBEAT,
)
if owed is False:
    ok("F: reconcile() owed=False inside the heartbeat window")
else:
    fail(f"F: reconcile() owed not False inside the window: {owed!r}")

# plan empty -> not owed regardless of elapsed.
owed, _ = mod.reconcile(
    [{"ts": STALE_REFIRE_TS, "decision": "immediate-refire", "detail": ""}],
    plan_nonempty=False, now_iso=NOW_40MIN, heartbeat_secs=HEARTBEAT,
)
if owed is False:
    ok("F: reconcile() owed=False when the plan is empty")
else:
    fail(f"F: reconcile() owed not False on an empty plan: {owed!r}")

# last decision is idle -> not owed.
owed, _ = mod.reconcile(
    [{"ts": STALE_REFIRE_TS, "decision": "idle: no dispatchable work",
      "detail": ""}],
    plan_nonempty=True, now_iso=NOW_40MIN, heartbeat_secs=HEARTBEAT,
)
if owed is False:
    ok("F: reconcile() owed=False when the last decision is idle")
else:
    fail(f"F: reconcile() owed not False on a prior idle decision: {owed!r}")

# a fresh refire AFTER the stale one is the last decision -> the prior fired.
owed, _ = mod.reconcile(
    [{"ts": STALE_REFIRE_TS, "decision": "immediate-refire", "detail": ""},
     {"ts": NOW_1MIN, "decision": "immediate-refire", "detail": ""}],
    plan_nonempty=True, now_iso=NOW_40MIN, heartbeat_secs=HEARTBEAT,
)
if owed is False:
    ok("F: reconcile() owed=False when a fresh refire is the last decision")
else:
    fail(f"F: reconcile() owed not False with a fresh last decision: {owed!r}")

# empty log -> not owed.
owed, _ = mod.reconcile(
    [], plan_nonempty=True, now_iso=NOW_40MIN, heartbeat_secs=HEARTBEAT,
)
if owed is False:
    ok("F: reconcile() owed=False on an empty log")
else:
    fail(f"F: reconcile() owed not False on an empty log: {owed!r}")


# ---------------------------------------------------------------------------
# G — --help smoke.
# ---------------------------------------------------------------------------
proc = subprocess.run([sys.executable, GUARD, "--help"],
                      capture_output=True, text=True)
if proc.returncode == 0 and "refire" in (proc.stdout + proc.stderr).lower():
    ok("G: --help exits 0 with recognizable usage")
else:
    fail(f"G: --help exit {proc.returncode}; out={proc.stdout!r}")


sys.exit(FAIL)
