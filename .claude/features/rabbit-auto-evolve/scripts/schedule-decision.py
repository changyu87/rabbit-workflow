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

Emitted JSON:
  - {"decision": "immediate-refire", "scheduler": "crontab"|"croncreate",
     "prompt": "/rabbit-auto-evolve start", "when": "~1min",
     "croncreate": {"cron": <near-now expr>,
                    "prompt": "/rabbit-auto-evolve start",
                    "durable": false, "recurring": false},
     "crontab_hint": <transient/at-style hint for the dispatcher>}
  - {"decision": "idle", "detail": "rely on heartbeat"}

Resolution:
  - fetch-queue.py via RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD when set (tests
    inject a shim), else the sibling scripts/fetch-queue.py.
  - detect-scheduler.py is the sibling script.
  - state dir (for the log) via RABBIT_AUTO_EVOLVE_STATE_DIR.

Exit code is always 0 (the verdict is carried in `decision`); non-zero only
if fetch-queue.py itself errors.

Version: 1.0.0
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

PROMPT = "/rabbit-auto-evolve start"
# A near-now one-shot expression on the croncreate path. The minute (e.g. the
# next-but-one wildcard "*/1" one-shot) avoids the :00/:30 marks per
# CronCreate guidance; the dispatcher cancels it after it fires (recurring
# false). We emit a "* * * * *" minute-cadence one-shot the dispatcher fires
# once (~1 min) and removes.
ONESHOT_CRON = "*/1 * * * *"


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
        result = {
            "decision": "immediate-refire",
            "scheduler": scheduler,
            "prompt": PROMPT,
            "when": "~1min",
            "croncreate": {
                "cron": ONESHOT_CRON,
                "prompt": PROMPT,
                "durable": False,
                "recurring": False,
            },
            "crontab_hint": (
                "schedule a transient one-shot ~1min out (an `at`-style or "
                "self-removing crontab entry) that runs "
                "`/rabbit-auto-evolve start` in a fresh context"
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
