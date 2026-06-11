#!/usr/bin/env python3
"""tick-jitter.py — the empirical CronCreate jitter offset (Inv 56, issue #881).

CronCreate applies a DETERMINISTIC per-job jitter to recurring tasks: a
recurring job fires up to 10% of its period late, capped at 15 min (CronCreate's
own documented bound). On an idle session this is a stable constant, NOT a range
and NOT idle-gating — the `13,43 * * * *` (30-min period) heartbeat fired a
constant +13 min late every time (ETA 21:43 fired 21:56, 22:13 fired 22:26,
22:43 fired 22:56). The CronCreate constraint that jobs fire only while the REPL
is idle (never mid-query) means a boundary missed mid-query is DELIVERED at the
next idle moment, not silently skipped; on an idle session every boundary is
delivered on time-plus-jitter, which is why the offset is a stable constant.

This script OWNS that value for rabbit-auto-evolve. It computes the offset as the
MEDIAN of `actual_fire_time − nearest_prior_cron_boundary` over the recent fires
recorded in `<state_dir>/tick.log` (Inv 36; each JSON line carries an ISO-8601
UTC `ts`), and persists it to the rabbit-auto-evolve-owned state artifact
`<state_dir>/auto-evolve-tick-jitter.json` so other features (e.g. the contract
feature's Stop line) can READ the value WITHOUT importing this feature.

When there is NO recorded fire history, `observed_jitter_minutes` falls back to
the documented cold-start bound `min(15, ceil(period_minutes * 0.10))` and
`cold_start` is set true — clearly a fallback, NOT the empirical value.

Subcommands:
  show     Compute and emit the offset record as JSON on stdout (no write).
  compute  Compute and persist the record to the state artifact (also echoes it).

Next-fire ETA (issue #1154): the displayed next-tick ETA was STALE/FROZEN across
refires because both the banner and the contract Stop line derived it solely from
the recurring heartbeat cron edge in `.claude/scheduled_tasks.json` — so while the
loop self-scheduled immediate-refire one-shots ~2 min out (Inv 33), the ETA still
showed the next heartbeat boundary (up to 30 min away) and never advanced with the
live schedule. This script now also derives the ACTUAL next scheduled CronCreate
event from the dispatcher-injected CronList snapshot (RABBIT_AUTO_EVOLVE_CRON_LIST,
the same channel schedule-decision.py reads): the EARLIEST upcoming fire across all
live entries (the pending refire AND the heartbeat), persisted as `next_fire_at`.
When no snapshot is injected `next_fire_at` is null and the consumer falls back to
the heartbeat-cadence computation. The wall-clock is overridable via
RABBIT_AUTO_EVOLVE_NOW (ISO-8601) for deterministic tests.

Artifact / stdout schema:
  {
    "schema_version": "1.1.0",
    "observed_jitter_minutes": <int >= 0>,
    "period_minutes": <int>,
    "sample_count": <int>,           # recorded fires used (0 on cold start)
    "cold_start": <bool>,
    "next_fire_at": <ISO-8601 UTC | null>,  # actual next scheduled fire (#1154)
    "computed_at": <ISO-8601 UTC>,
    "owner": "rabbit-workflow team",
    "deprecation_criterion": "..."
  }

State-dir resolution honors RABBIT_AUTO_EVOLVE_STATE_DIR (matching tick-log.py /
update-state.py), else `<cwd>/.rabbit`. The cadence source is the repo-root
`.claude/scheduled_tasks.json` (the tasks[] entry whose prompt references
rabbit-auto-evolve), repo_root via RABBIT_AUTO_EVOLVE_REPO_ROOT else cwd. Always
exits 0 (a degraded/absent source yields a graceful cold-start record).

Version: 1.1.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys

SCHEMA_VERSION = "1.1.0"
ARTIFACT_NAME = "auto-evolve-tick-jitter.json"
TICK_LOG_NAME = "tick.log"
OWNER = "rabbit-workflow team"
DEPRECATION = (
    "when Claude Code or rabbit gains a native always-on autonomous-agent "
    "mode that supersedes this skill"
)


def _state_dir() -> str:
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_cron_minutes(field: str) -> set:
    """Parse a crontab MINUTE field into the set of minutes (0..59) it fires on.
    Supports the cadence forms the heartbeat uses: `*`, comma lists (`13,43`),
    and step expressions (`*/15`). Returns the empty set for any unparseable
    field. Mirrors banner-status.py._parse_cron_minutes (kept in sync; the
    contract helper is a private internal, so this small computation is
    duplicated rather than imported across the boundary)."""
    field = field.strip()
    if field == "*":
        return set(range(60))
    if field.startswith("*/"):
        try:
            step = int(field[2:])
        except ValueError:
            return set()
        if step <= 0:
            return set()
        return set(range(0, 60, step))
    minutes = set()
    for part in field.split(","):
        part = part.strip()
        if not part.isdigit():
            return set()
        m = int(part)
        if not 0 <= m <= 59:
            return set()
        minutes.add(m)
    return minutes


def _read_cadence_minutes() -> set:
    """Return the heartbeat's cron MINUTE set from the repo-root cadence source,
    or the empty set on any absent/unreadable/unparseable/no-match condition."""
    path = os.path.join(_repo_root(), ".claude", "scheduled_tasks.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict):
        return set()
    cron = None
    for task in data.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        if "rabbit-auto-evolve" in str(task.get("prompt", "")):
            cron = task.get("cron")
            break
    if not isinstance(cron, str):
        return set()
    parts = cron.split()
    if not parts:
        return set()
    return _parse_cron_minutes(parts[0])


def _period_minutes(minutes: set) -> int:
    """The cadence period: the smallest gap (mod 60) between consecutive fire
    minutes. A single fire-minute per hour is a 60-min period; an all-minute
    cron is a 1-min period. Returns 0 for an empty set (caller guards)."""
    if not minutes:
        return 0
    ordered = sorted(minutes)
    if len(ordered) == 1:
        return 60
    gaps = []
    for i in range(len(ordered)):
        nxt = ordered[(i + 1) % len(ordered)]
        gap = (nxt - ordered[i]) % 60
        if gap == 0:
            gap = 60
        gaps.append(gap)
    return min(gaps)


def _cold_fallback(period_minutes: int) -> int:
    """The documented CronCreate cold-start bound: up to 10% of the period late,
    capped at 15 min — min(15, ceil(period_minutes * 0.10))."""
    if period_minutes <= 0:
        return 0
    return min(15, math.ceil(period_minutes * 0.10))


def _read_fire_times() -> list:
    """Parse the ISO-8601 UTC `ts` of every recorded fire in tick.log (Inv 36),
    newest-last. Returns a list of timezone-aware datetimes; silently skips
    malformed lines and returns [] when the log is absent/unreadable."""
    path = os.path.join(_state_dir(), TICK_LOG_NAME)
    fires = []
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        ts = rec.get("ts") if isinstance(rec, dict) else None
        if not isinstance(ts, str):
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        fires.append(dt)
    return fires


def _offset_minutes(fire: datetime.datetime, cadence_minutes: set) -> int:
    """The minutes between `fire` and its NEAREST PRIOR cron boundary (the most
    recent wall-clock minute in `cadence_minutes` at or before the fire). Walks
    back at most 60 minutes (the max period). Returns 0 when the fire minute is
    itself a boundary."""
    base = fire.replace(second=0, microsecond=0)
    for delta in range(0, 61):
        candidate = base - datetime.timedelta(minutes=delta)
        if candidate.minute in cadence_minutes:
            return delta
    return 0


def _now() -> datetime.datetime:
    """Wall-clock used solely to derive the actual-next-fire ETA (#1154).
    Overridable via RABBIT_AUTO_EVOLVE_NOW (ISO-8601) for deterministic tests —
    a `Z` suffix yields an aware UTC datetime, a bare value a naive one — falling
    back to the real UTC clock. A malformed override degrades to the real clock."""
    raw = os.environ.get("RABBIT_AUTO_EVOLVE_NOW")
    if raw:
        try:
            return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.datetime.now(datetime.timezone.utc)


def _cron_list_snapshot() -> list:
    """Parse the dispatcher-injected CronList snapshot from
    RABBIT_AUTO_EVOLVE_CRON_LIST (a JSON array). Absent/malformed → []. A script
    cannot call CronList itself, so the dispatcher passes its result through this
    env var — the same channel schedule-decision.py reads (Inv 33)."""
    raw = os.environ.get("RABBIT_AUTO_EVOLVE_CRON_LIST")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _next_fire_for_cron(cron, now: datetime.datetime):
    """The next wall-clock fire of a `M H * * *`-shaped cron at/after `now+1min`,
    or None if the MINUTE/HOUR fields are unparseable. Matches the MINUTE field
    against the HOUR field (`*` = every hour, a single integer = that hour),
    walking forward minute-by-minute up to 24h. The day-of-month/month/weekday
    fields are treated as unrestricted — the shape both the recurring heartbeat
    (`13,43 * * * *`) and the pinned refire one-shot (`M H * * *`, Inv 33) use."""
    if not isinstance(cron, str):
        return None
    parts = cron.split()
    if len(parts) < 2:
        return None
    minutes = _parse_cron_minutes(parts[0])
    if not minutes:
        return None
    hour_field = parts[1].strip()
    if hour_field == "*":
        hours = set(range(24))
    elif hour_field.isdigit() and 0 <= int(hour_field) <= 23:
        hours = {int(hour_field)}
    else:
        return None
    candidate = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    for _ in range(1440):
        if candidate.minute in minutes and candidate.hour in hours:
            return candidate
        candidate += datetime.timedelta(minutes=1)
    return None


def _next_fire_at(now: datetime.datetime):
    """#1154: the ACTUAL next scheduled CronCreate event — the EARLIEST upcoming
    fire across every entry in the dispatcher-injected CronList snapshot (the
    pending immediate-refire one-shot AND the recurring heartbeat). Returns an
    ISO-8601 UTC string, or None when no snapshot is injected or no entry yields
    a parseable upcoming fire (the consumer then falls back to the heartbeat
    cadence). This is what makes the displayed ETA track the live schedule rather
    than freezing on a stale heartbeat cron edge across refires."""
    snapshot = _cron_list_snapshot()
    if not snapshot:
        return None
    fires = []
    for entry in snapshot:
        if not isinstance(entry, dict):
            continue
        fire = _next_fire_for_cron(entry.get("cron"), now)
        if fire is not None:
            fires.append(fire)
    if not fires:
        return None
    earliest = min(fires)
    if earliest.tzinfo is not None:
        earliest = earliest.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return earliest.strftime("%Y-%m-%dT%H:%M:%SZ")


def _median(values: list) -> int:
    """Integer median of a non-empty list (lower-middle on an even count, so
    the result is always an observed sample — stable for the jitter constant)."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    # Even count: average the two central samples, rounded to the nearest int.
    return int(round((ordered[mid - 1] + ordered[mid]) / 2))


def compute_record() -> dict:
    """Build the jitter record. Empirical (median over recorded fires) when a
    fire history exists for the parseable cadence; otherwise the cold-start
    fallback bound. Always returns a full-schema dict."""
    cadence_minutes = _read_cadence_minutes()
    period = _period_minutes(cadence_minutes)
    record = {
        "schema_version": SCHEMA_VERSION,
        "observed_jitter_minutes": 0,
        "period_minutes": period,
        "sample_count": 0,
        "cold_start": True,
        # #1154: the actual next scheduled fire derived from the live CronList
        # snapshot (null when no snapshot is injected — the consumer then falls
        # back to the heartbeat cadence). Always present in the schema.
        "next_fire_at": _next_fire_at(_now()),
        "computed_at": _now_iso(),
        "owner": OWNER,
        "deprecation_criterion": DEPRECATION,
    }
    if not cadence_minutes:
        # No parseable cadence — nothing to anchor offsets against. Degrade to a
        # zero cold-start record (caller/banner falls back to its bare line).
        return record
    fires = _read_fire_times()
    offsets = [_offset_minutes(f, cadence_minutes) for f in fires]
    if offsets:
        record["observed_jitter_minutes"] = _median(offsets)
        record["sample_count"] = len(offsets)
        record["cold_start"] = False
    else:
        record["observed_jitter_minutes"] = _cold_fallback(period)
        record["cold_start"] = True
    return record


def _persist(record: dict) -> str:
    state_dir = _state_dir()
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, ARTIFACT_NAME)
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    return path


def cmd_show(_args) -> int:
    print(json.dumps(compute_record(), indent=2))
    return 0


def cmd_compute(_args) -> int:
    record = compute_record()
    _persist(record)
    print(json.dumps(record, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute the empirical CronCreate jitter offset (Inv 56 / #881) "
            "from .rabbit/tick.log and persist it to "
            ".rabbit/auto-evolve-tick-jitter.json. Honors "
            "RABBIT_AUTO_EVOLVE_STATE_DIR / RABBIT_AUTO_EVOLVE_REPO_ROOT."
        )
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_show = sub.add_parser("show", help="emit the offset record JSON (no write)")
    p_show.set_defaults(func=cmd_show)
    p_compute = sub.add_parser("compute", help="persist the offset record")
    p_compute.set_defaults(func=cmd_compute)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
