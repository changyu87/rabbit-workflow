#!/usr/bin/env python3
"""refire-guard.py — make a DROPPED immediate-refire deterministically
observable at the next tick start (Inv 65, issue #1051).

Usage:
  refire-guard.py --plan-nonempty   # the dispatchable plan is non-empty
  refire-guard.py --plan-empty      # the dispatchable plan is empty

Phase 12 `schedule-decision.py` emits `immediate-refire` when dispatchable work
remains (Inv 33), and the dispatcher must then `CronCreate` the one-shot. That
`CronCreate` is an irreducible CLAUDE tool action a script cannot make — and
NOTHING verified it happened. If the dispatcher ended the turn WITHOUT creating
the one-shot, the loop silently stopped self-continuing (degraded to heartbeat
cadence, or stalled) — the silent-stop failure mode the Scheduling section
(Inv 32-33) claims to have eliminated. `CronCreate` stays Claude-only, so this
guard makes the DROP deterministically OBSERVABLE rather than scripting the
create.

The breadcrumb already exists: `schedule-decision.py` logs every decision to
`.rabbit/tick.log` (Inv 36), and an `immediate-refire` line carries an ISO-8601
`ts`. A promptly-fired refire enters a NEW tick within the pinned ~1-min window
and that tick logs a FRESH schedule decision; so the LAST `tick.log` decision
being a STALE `immediate-refire` (no newer decision after it) is the
deterministic signature of a refire that never fired.

At tick start `run-tick-phases.py pre-dispatch` invokes this guard AFTER phases
3-5 compute the plan, passing `--plan-nonempty` / `--plan-empty`. The refire is
OWED-BUT-NOT-FIRED iff ALL hold:

  - the LAST tick.log schedule decision is `immediate-refire`;
  - the dispatchable plan is STILL non-empty (passed in, NOT re-derived —
    Inv 33's selection_order is the authority);
  - MORE than a heartbeat-interval has elapsed since that decision's `ts`, so
    the refire clearly did NOT fire promptly.

When owed, a LOUD warning is appended to tick.log and the CLI emits
`{"refire_owed": true, "detail": ...}`; the dispatcher MUST act on it (create
the one-shot). The guard DETECTS + SURFACES; it NEVER calls `CronCreate`. It
prefers a false-NEGATIVE (wait one more heartbeat) over a false-POSITIVE (a
spurious owed-warning), so a still-fresh refire, a prior `idle`, a now-empty
plan, or an absent log all yield `refire_owed: false`.

  state_dir via RABBIT_AUTO_EVOLVE_STATE_DIR (mirroring tick-log.py), else
  <cwd>/.rabbit.
  heartbeat seconds via RABBIT_AUTO_EVOLVE_CADENCE (minutes), else 30 min.
  `now` via RABBIT_AUTO_EVOLVE_NOW (ISO-8601) for deterministic tests.

Exit code is always 0 (the verdict is carried in `refire_owed`).

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import importlib.util
import json
import os
import sys

LOG_NAME = "tick.log"
REFIRE_DECISION = "immediate-refire"
DEFAULT_HEARTBEAT_SECS = 1800  # 30 min — the default recurring-heartbeat cadence.


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _heartbeat_secs():
    """The recurring-heartbeat cadence in seconds. Derived from the same
    RABBIT_AUTO_EVOLVE_CADENCE (minutes) install-cron.py honors; default 30 min.
    The threshold past which a refire that never logged a fresh decision is
    judged dropped (a prompt refire fires within ~1 min, far inside this)."""
    raw = os.environ.get("RABBIT_AUTO_EVOLVE_CADENCE")
    if raw:
        try:
            mins = int(raw)
            if 1 <= mins <= 59:
                return mins * 60
        except ValueError:
            pass
    return DEFAULT_HEARTBEAT_SECS


def _now_iso():
    """The current wall-clock ISO-8601 UTC, overridable via
    RABBIT_AUTO_EVOLVE_NOW for deterministic tests."""
    override = os.environ.get("RABBIT_AUTO_EVOLVE_NOW")
    if override:
        return override
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_iso(ts):
    """Parse an ISO-8601 UTC `...Z` timestamp into an aware datetime, or None
    on a malformed value (Python 3.7's fromisoformat does not accept `Z`)."""
    if not isinstance(ts, str):
        return None
    try:
        naive = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None
    return naive.replace(tzinfo=datetime.timezone.utc)


def _read_log_lines():
    """Return the non-blank lines of <state_dir>/tick.log, or [] when absent."""
    path = os.path.join(_state_dir(), LOG_NAME)
    try:
        with open(path) as f:
            return [ln for ln in f.read().splitlines() if ln.strip()]
    except OSError:
        return []


def reconcile(log_lines, plan_nonempty, now_iso, heartbeat_secs):
    """PURE predicate (Inv 65): was an immediate-refire OWED but never fired?

    Returns `(refire_owed: bool, detail: str)`. `log_lines` is the list of raw
    JSON lines from tick.log (oldest first); the LAST parseable schedule
    decision is authoritative. `refire_owed` is True iff ALL hold:

      - the last tick.log schedule decision is `immediate-refire`;
      - `plan_nonempty` (the dispatchable plan is still non-empty);
      - more than `heartbeat_secs` has elapsed between that decision's `ts` and
        `now_iso` (the refire clearly did not fire promptly).

    Any other case (a fresh refire / a prior idle as the last decision, an empty
    plan, an unparseable or absent log) returns False — the guard prefers a
    false-negative over a false-positive. No I/O; safe to unit-test."""
    last = None
    for raw in log_lines:
        try:
            rec = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(rec, dict) and "decision" in rec:
            last = rec
    if last is None:
        return False, "no prior tick.log decision"
    decision = last.get("decision") or ""
    if not decision.startswith(REFIRE_DECISION):
        return False, f"last decision was not immediate-refire ({decision!r})"
    if not plan_nonempty:
        return False, "dispatchable plan is now empty; heartbeat backstop is correct"
    now = _parse_iso(now_iso)
    then = _parse_iso(last.get("ts"))
    if now is None or then is None:
        return False, "unparseable timestamp"
    elapsed = (now - then).total_seconds()
    if elapsed <= heartbeat_secs:
        return False, f"refire decided {int(elapsed)}s ago; still inside the window"
    return True, (
        f"immediate-refire decided {int(elapsed)}s ago (> heartbeat "
        f"{heartbeat_secs}s) with a still-non-empty plan and no fresher "
        f"decision — the dispatcher likely dropped the one-shot CronCreate"
    )


def _log(decision, detail):
    """Best-effort append via tick-log.py (hyphenated name -> file spec)."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        spec = importlib.util.spec_from_file_location(
            "tick_log", os.path.join(here, "tick-log.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.append(decision, detail)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"refire-guard: tick-log append failed: {e}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile the PRIOR tick's immediate-refire decision at "
                    "tick start: surface a dropped refire (owed but never "
                    "fired) deterministically (Inv 65 / #1051)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan-nonempty", dest="plan_nonempty",
                       action="store_true",
                       help="the dispatchable plan is non-empty this tick")
    group.add_argument("--plan-empty", dest="plan_nonempty",
                       action="store_false",
                       help="the dispatchable plan is empty this tick")
    args = parser.parse_args()

    owed, detail = reconcile(
        _read_log_lines(), args.plan_nonempty, _now_iso(), _heartbeat_secs(),
    )
    if owed:
        # The LOUD, deterministic surface: a tick.log warning the dispatcher
        # (and any cross-session reader) sees. The decision token carries both
        # `refire` and `owed` so it is unmistakable.
        _log("refire-owed: dropped immediate-refire", detail)
    json.dump({"refire_owed": owed, "detail": detail}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
