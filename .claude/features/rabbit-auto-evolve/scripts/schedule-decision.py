#!/usr/bin/env python3
"""schedule-decision.py — decide immediate-refire vs idle at tick end.

Usage:
  schedule-decision.py       # emit the schedule decision JSON on stdout

Per rabbit-auto-evolve spec.md Inv 33 (D1, issue #521 + #509), at the END of
a tick (and equivalently at a heartbeat) the loop decides whether to schedule
the next tick based on open work:

  - queue NON-EMPTY -> schedule the next tick NEAR-IMMEDIATELY (~1 min) in a
    FRESH Claude context as a one-shot, then the dispatcher ends the turn.
  - queue EMPTY     -> schedule nothing; rely on the recurring heartbeat.

Open-work presence is determined AUTHORITATIVELY by invoking the EXISTING
fetch-queue.py and counting items (this script does NOT re-derive the queue).
The scheduler mechanism (crontab vs croncreate) is read from
detect-scheduler.py. The decision is logged via tick-log.py.

A script CANNOT call `CronCreate` — so on the croncreate path this script only
emits the one-shot params; the DISPATCHER reads the JSON at phase 11 and
performs the actual `CronCreate(...)` (the irreducible Claude action).

The refire wake-up fires the INTERNAL `tick` (the scripted phase-walk that
respects but never deletes the stop marker), NOT the USER-intent `start` whose
Inv 19 stop-cancel would resurrect a user-halted loop on a MACHINE wake-up.

Refire dedup (Inv 33, issue #559): every tick scheduled a refire one-shot but
nothing cancelled a prior pending one, so retried/overlapping ticks PILED UP
refires that fired together (an observed double-fire). The fix gives the refire
prompt a recognizable MARKER (`/rabbit-auto-evolve tick #refire`) so it is
distinguishable from the recurring heartbeat (bare `/rabbit-auto-evolve tick`),
exposes the PURE predicate `is_refire_oneshot(entry)`, and emits a
`dispatcher_actions` block (delete prior refires, preserve the heartbeat,
create exactly one new refire) computed from the dispatcher-injected CronList
snapshot (RABBIT_AUTO_EVOLVE_CRON_LIST). The actual CronList/CronDelete/
CronCreate are DISPATCHER (Claude) actions; this script only emits the
deterministic instruction set.

Emitted JSON:
  - {"decision": "immediate-refire", "scheduler": "crontab"|"croncreate",
     "prompt": "/rabbit-auto-evolve tick #refire", "when": "~1min",
     "croncreate": {"cron": <near-now expr>,
                    "prompt": "/rabbit-auto-evolve tick #refire",
                    "durable": false, "recurring": false},
     "dispatcher_actions": {"delete_refire_ids": [...],
                            "preserve_heartbeat_ids": [...],
                            "create_refire": {<the one-shot to CronCreate>}},
     "crontab_hint": <transient/at-style hint for the dispatcher>}
  - {"decision": "idle", "detail": "rely on heartbeat"}

Resolution:
  - fetch-queue.py via RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD when set (tests
    inject a shim), else the sibling scripts/fetch-queue.py.
  - detect-scheduler.py is the sibling script.
  - state dir (for the log) via RABBIT_AUTO_EVOLVE_STATE_DIR.

Exit code is always 0 (the verdict is carried in `decision`); non-zero only
if fetch-queue.py itself errors.

Version: 1.3.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

# The refire wake-up fires the INTERNAL `tick` (the scripted phase-walk that
# RESPECTS the stop marker at phase 0 and NEVER deletes it), NOT the USER-intent
# `start` (whose Inv 19 stop-cancel would silently resurrect a user-halted
# loop). A MACHINE wake-up must never inherit a user-intent's stop-cancelling
# semantics.
#
# Inv 33 (#559): the refire one-shot's prompt carries a recognizable refire
# MARKER so it is distinguishable from the RECURRING heartbeat (whose prompt is
# the bare `/rabbit-auto-evolve tick`). Without this signature the dispatcher's
# CronList dedup cannot tell a prior pending refire from the heartbeat — the
# root cause of the #559 refire pile-up / double-fire.
TICK_COMMAND = "/rabbit-auto-evolve tick"
REFIRE_MARKER = "#refire"
PROMPT = f"{TICK_COMMAND} {REFIRE_MARKER}"


# Inv 33 arm-time-skid buffer (#748): the pinned one-shot minute is the current
# minute + 2, NOT + 1. The dispatcher arms the one-shot via a
# CronList -> CronDelete -> CronCreate dedup round-trip (Inv 33) that eats
# several seconds. With a +1 pinned minute, a decision landing in the final
# seconds of a wall-clock minute let that round-trip CROSS the minute boundary,
# so the pinned minute became the CURRENT (already-started) minute; because this
# is a one-shot pinned to "M H * * *" (not "*/1"), its next match was that same
# minute ~24h later — the refire was effectively dropped (~14% of the time). A
# 2-minute buffer keeps the pinned minute STRICTLY in the future even after the
# multi-second round-trip, while staying "~1 min" responsive. Keep it
# minutes-based (cron has no sub-minute granularity).
_ONESHOT_MINUTE_BUFFER = 2


def _pinned_oneshot_cron(now=None):
    """Return a PINNED near-future cron expression "M H * * *" for the
    croncreate one-shot path (Inv 33 pinned-minute amendment, issue #531;
    arm-time-skid buffer, issue #748).

    The minute is the current minute + 2 (a 2-minute buffer, see
    `_ONESHOT_MINUTE_BUFFER`) and the hour is that minute's hour. A PINNED
    "M H * * *" form (never the fragile every-minute "*/1 * * * *") means the
    catastrophic failure mode — the dispatcher dropping `recurring: false` (a
    CronCreate default is recurring) — fires at most ONCE PER DAY at minute M
    instead of an every-minute storm.

    The 2-minute buffer (#748) guarantees the pinned minute is strictly in the
    future even after the dispatcher's multi-second CronList -> CronDelete ->
    CronCreate dedup round-trip (Inv 33) crosses a wall-clock minute boundary; a
    +1 buffer was dropped ~14% of the time when a decision landed in the final
    seconds of a minute.

    The minute also AVOIDS the :00 and :30 marks per CronCreate guidance: when
    the buffered minute lands on 0 or 30 it is nudged forward by one minute
    (carrying into the next hour on rollover).

    `now` is injectable for deterministic tests; it defaults to the local wall
    clock (schedule-decision.py is an ordinary Python script, not a
    workflow-sandboxed one, so reading the wall clock is allowed).
    """
    if now is None:
        now = datetime.now()
    target = now + timedelta(minutes=_ONESHOT_MINUTE_BUFFER)
    if target.minute in (0, 30):
        target = target + timedelta(minutes=1)
    return f"{target.minute} {target.hour} * * *"


def is_refire_oneshot(entry):
    """Inv 33 (#559): PURE predicate — is `entry` (a `CronList` row) one of OUR
    immediate-refire one-shots, as opposed to the recurring heartbeat?

    True iff ALL hold:
      - the prompt carries the refire MARKER (`#refire`), AND
      - the entry is NON-recurring, AND
      - the entry is NON-durable.

    The recurring/durable heartbeat (Inv 32/34) carries the bare
    `/rabbit-auto-evolve tick` prompt with no marker, so it is NEVER matched —
    the dedup can therefore never select the heartbeat for removal. A marker
    that somehow appears on a RECURRING or DURABLE entry is also excluded: a
    refire is by definition a one-shot, and we must never tear down a recurring
    schedule.

    No I/O — `entry` is a plain dict; safe to unit-test in isolation.
    """
    if not isinstance(entry, dict):
        return False
    prompt = entry.get("prompt") or ""
    if REFIRE_MARKER not in prompt:
        return False
    if entry.get("recurring"):
        return False
    if entry.get("durable"):
        return False
    return True


def _is_heartbeat(entry):
    """A recurring OR durable entry whose prompt is NOT a refire marker is
    treated as a heartbeat to PRESERVE (Inv 33). This is the complement used
    only to populate `preserve_heartbeat_ids` for dispatcher transparency; the
    delete decision is driven solely by `is_refire_oneshot`."""
    if not isinstance(entry, dict):
        return False
    if is_refire_oneshot(entry):
        return False
    return bool(entry.get("recurring") or entry.get("durable"))


def _cron_list_snapshot():
    """Parse the dispatcher-injected `CronList` snapshot from the
    RABBIT_AUTO_EVOLVE_CRON_LIST env var (a JSON array). Absent or malformed →
    treated as empty (Inv 33). A script cannot call `CronList` itself, so the
    DISPATCHER passes its `CronList` result through this env var at phase 11."""
    raw = os.environ.get("RABBIT_AUTO_EVOLVE_CRON_LIST")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _entry_id(entry):
    """The dispatcher's id for a CronList row (best-effort across shapes)."""
    if not isinstance(entry, dict):
        return None
    for key in ("id", "cron_id", "name"):
        if entry.get(key):
            return entry[key]
    return None


def _dispatcher_actions(create_refire):
    """Inv 33 (#559): emit the EXPLICIT delete/preserve/create instruction set
    the DISPATCHER follows. A script cannot call CronList/CronDelete/CronCreate
    — those are Claude actions — so this computes, from the injected snapshot:

      - delete_refire_ids: ids of prior refire ONE-SHOTS to `CronDelete`
        (every entry matching `is_refire_oneshot`), so at most ONE refire is
        alive at a time;
      - preserve_heartbeat_ids: heartbeat ids the dispatcher MUST NOT delete;
      - create_refire: the single new refire to `CronCreate`.
    """
    snapshot = _cron_list_snapshot()
    delete_ids = [
        _entry_id(e) for e in snapshot
        if is_refire_oneshot(e) and _entry_id(e) is not None
    ]
    preserve_ids = [
        _entry_id(e) for e in snapshot
        if _is_heartbeat(e) and _entry_id(e) is not None
    ]
    return {
        "delete_refire_ids": delete_ids,
        "preserve_heartbeat_ids": preserve_ids,
        "create_refire": create_refire,
    }


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _fetch_queue_cmd():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD")
    if override:
        return [sys.executable, override]
    return [sys.executable, os.path.join(_script_dir(), "fetch-queue.py")]


def _open_work_count():
    """Invoke fetch-queue.py and return the number of open items. Raises
    RuntimeError on a fetch failure."""
    proc = subprocess.run(
        _fetch_queue_cmd(), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"fetch-queue failed (exit {proc.returncode}): {proc.stderr}"
        )
    try:
        items = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"fetch-queue emitted invalid JSON: {e}") from e
    return len(items) if isinstance(items, list) else 0


def _scheduler():
    """Run detect-scheduler.py and return "crontab" or "croncreate"."""
    proc = subprocess.run(
        [sys.executable, os.path.join(_script_dir(), "detect-scheduler.py")],
        capture_output=True, text=True,
    )
    try:
        return json.loads(proc.stdout).get("scheduler", "crontab")
    except (json.JSONDecodeError, AttributeError):
        return "crontab"


def _log(decision, detail):
    """Best-effort append via tick-log.py (hyphenated name -> file spec)."""
    try:
        spec = importlib.util.spec_from_file_location(
            "tick_log", os.path.join(_script_dir(), "tick-log.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.append(decision, detail)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"schedule-decision: tick-log append failed: {e}\n")


def decide():
    count = _open_work_count()
    if count > 0:
        scheduler = _scheduler()
        # The single refire to CronCreate (Inv 33). PROMPT carries the #refire
        # marker so this one-shot is later distinguishable from the heartbeat.
        create_refire = {
            "cron": _pinned_oneshot_cron(),
            "prompt": PROMPT,
            "durable": False,
            "recurring": False,
        }
        result = {
            "decision": "immediate-refire",
            "scheduler": scheduler,
            "prompt": PROMPT,
            "when": "~1min",
            "croncreate": dict(create_refire),
            # Inv 33 (#559): the EXPLICIT instruction set the dispatcher
            # follows — delete prior refire one-shots, preserve the heartbeat,
            # create exactly one new refire. Computed from the injected
            # CronList snapshot (RABBIT_AUTO_EVOLVE_CRON_LIST).
            "dispatcher_actions": _dispatcher_actions(dict(create_refire)),
            "crontab_hint": (
                "schedule a transient one-shot ~1min out (an `at`-style or "
                "self-removing crontab entry) that runs "
                f"`{PROMPT}` in a fresh context"
            ),
        }
        _log("immediate-refire", f"open work={count}, scheduler={scheduler}")
        return result
    result = {"decision": "idle", "detail": "rely on heartbeat"}
    _log("idle: no work", "queue empty")
    return result


def main():
    argparse.ArgumentParser(
        description="Decide the end-of-tick schedule: immediate fresh-context "
                    "refire when work remains, else idle (Inv 33 / D1 / "
                    "#521). Emits the decision JSON on stdout."
    ).parse_args()
    try:
        result = decide()
    except RuntimeError as e:
        sys.stderr.write(f"schedule-decision: {e}\n")
        return 1
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
