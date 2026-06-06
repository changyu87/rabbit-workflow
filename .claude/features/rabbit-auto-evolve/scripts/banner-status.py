#!/usr/bin/env python3
"""banner-status.py — owns the active-banner line-2 text variants.

Per rabbit-auto-evolve spec.md Inv 22 (added v0.7.5 for issue #380),
this CLI inspects rabbit-auto-evolve's runtime markers at the repo root
and emits a JSON object on stdout describing the active banner. Always
exits 0.

When `.rabbit-auto-evolve-active` is absent:

  {"active": false, "line1": null, "line2": null}

When `.rabbit-auto-evolve-active` is present:

  {
    "active": true,
    "line1": {"text": "AUTONOMOUS-EVOLVE MODE ACTIVE", "icon": "...", "color": "red"},
    "line2": {"text": "<per precedence>", "icon": "...", "color": "..."}
  }

Line-2 precedence (first match wins):

  | adjunct marker(s)                       | substring                            | icon | color  |
  |-----------------------------------------|--------------------------------------|------|--------|
  | .rabbit-auto-evolve-aborted (highest)   | loop aborted on safety violation     | 🛑   | red    |
  | .rabbit-auto-evolve-restart-needed      | resume after restart                 | 🔁   | yellow |
  | .rabbit-auto-evolve-running             | loop in progress                     | 🔄   | yellow |
  | none, state-file ABSENT (#793)          | auto-evolve configured — restart …   | ⏸    | yellow |
  | none, state-file PRESENT                | paste: /rabbit-auto-evolve start     | ▶    | yellow |

The two `none` sub-cases (#793) split the lowest-priority branch by the
presence of `.rabbit/auto-evolve-state.json` (only start-loop.py creates it on
the first `start`). ABSENT means the post-`on`/pre-`start` window — configured
but never started, a restart is pending — so the restart-pending line2 is
emitted VERBATIM the same as the symmetric Stop line
(`contract.lib.runtime.emit_auto_evolve_stop_line`, Inv 55) so SessionStart
and Stop agree. PRESENT retains the existing idle/active line.

#844/#881: only the PRESENT (started-then-idle) line is extended with the same
next-tick ETA the Stop line carries — for SessionStart<->Stop symmetry. The
boundary is computed by mirroring contract Inv 55's cadence computation (the
contract helper is a private internal, so rabbit-auto-evolve mirrors it rather
than depending on contract internals): read the heartbeat cron from repo-root
`.claude/scheduled_tasks.json` and walk to the next matching wall-clock minute
from an injectable `now`. The line degrades to the bare idle text when the
cadence source is absent/unparseable. The four priority-marker lines and the
restart-pending line never carry an ETA. The wall-clock is overridable via
`RABBIT_AUTO_EVOLVE_NOW` (ISO-8601) for deterministic tests.

#881 (third reopen): the displayed ETA is a single EXACT wall-clock time
`paste: /rabbit-auto-evolve start, next tick HH:MM` — one bare timestamp, no
range and no qualifier. It is the next cron boundary PLUS the deterministic
CronCreate jitter offset (Inv 56). CronCreate adds a deterministic per-job
jitter to recurring tasks: a recurring job fires up to 10% of its period late,
capped at 15 min. On an idle session this is a stable constant — the
`13,43 * * * *` (30-min period) heartbeat fired a constant +13 min late every
time (ETA 21:43 fired 21:56, 22:13 fired 22:26, 22:43 fired 22:56). The
constraint that jobs fire only while the REPL is idle (never mid-query) means a
boundary missed mid-query is DELIVERED at the next idle moment, not silently
skipped; on an idle session every boundary is delivered on time-plus-jitter, so
the offset is a stable constant. The offset is owned and persisted by
`tick-jitter.py` (Inv 56) at `.rabbit/auto-evolve-tick-jitter.json`
(`observed_jitter_minutes`); banner-status.py READS that value and adds it to
the boundary. When the artifact is absent it falls back to the documented
cold-start bound `min(15, ceil(period_minutes * 0.10))`.

Marker file contents (for aborted/restart-needed) are surfaced in the line2
text alongside the literal substring above when non-empty.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Ownership: `contract.lib.runtime.emit_auto_evolve_banner` is a pure subprocess
dispatcher — it delegates both line-1 and line-2 content to this script and
maps the JSON result to the SessionStart banner. This script is therefore the
single owner of all line-2 variants (including `running`), every one of which
is surfaced at SessionStart.

Version: 1.6.0
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

ACTIVE_MARKER = ".rabbit-auto-evolve-active"
RUNNING_MARKER = ".rabbit-auto-evolve-running"
RESTART_MARKER = ".rabbit-auto-evolve-restart-needed"
ABORTED_MARKER = ".rabbit-auto-evolve-aborted"

# #793: the loop-started signal. Only start-loop.py creates this on the first
# `start`; its ABSENCE marks the post-`on`/pre-`start` window (never started).
STATE_FILE = os.path.join(".rabbit", "auto-evolve-state.json")

# #881 (Inv 56): the rabbit-auto-evolve-owned jitter offset artifact tick-jitter.py
# persists. banner-status.py READS observed_jitter_minutes to add to the boundary.
JITTER_FILE = os.path.join(".rabbit", "auto-evolve-tick-jitter.json")

# #793: restart-pending line2 — VERBATIM the same as the Stop line in
# contract.lib.runtime so SessionStart and Stop agree.
RESTART_PENDING_TEXT = (
    "auto-evolve configured — restart Claude Code, then run "
    "/rabbit-auto-evolve start"
)


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _read_marker_reason(path: str) -> str:
    """Return stripped marker file content, or empty string on read failure."""
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _now() -> datetime.datetime:
    """Wall-clock used solely for the idle next-tick ETA. Overridable via the
    RABBIT_AUTO_EVOLVE_NOW env var (ISO-8601, e.g. 2026-06-04T14:20:00) so the
    ETA is deterministic in tests; falls back to the real clock otherwise. A
    malformed override degrades to the real clock (never crashes)."""
    raw = os.environ.get("RABBIT_AUTO_EVOLVE_NOW")
    if raw:
        try:
            return datetime.datetime.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.datetime.now()


def _parse_cron_minutes(field: str) -> set:
    """Parse a crontab MINUTE field into the set of minutes (0..59) it fires
    on. Supports the cadence forms the heartbeat actually uses: `*` (every
    minute), comma lists (`13,43`), and step expressions (`*/15`). Returns an
    empty set for any field it cannot parse (caller treats empty as "no
    parseable cron"). Mirrors contract.lib.runtime._parse_cron_minutes (#844):
    the helper is a private contract internal, so rabbit-auto-evolve mirrors
    the small computation rather than depending on contract internals."""
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


def _period_minutes(minutes: set) -> int:
    """The cadence period: the smallest gap (mod 60) between consecutive fire
    minutes. A single fire-minute per hour is a 60-min period. Mirrors
    tick-jitter.py._period_minutes (the cold-start fallback must match)."""
    if not minutes:
        return 0
    ordered = sorted(minutes)
    if len(ordered) == 1:
        return 60
    gaps = []
    for i in range(len(ordered)):
        gap = (ordered[(i + 1) % len(ordered)] - ordered[i]) % 60
        if gap == 0:
            gap = 60
        gaps.append(gap)
    return min(gaps)


def _jitter_offset_minutes(repo_root: str, period_minutes: int) -> int:
    """#881 (Inv 56): the deterministic CronCreate jitter offset to ADD to the
    next cron boundary. Reads `observed_jitter_minutes` from the
    rabbit-auto-evolve-owned artifact tick-jitter.py persists. When the artifact
    is absent/unreadable, falls back to the documented cold-start bound
    `min(15, ceil(period_minutes * 0.10))` (clearly a fallback, not empirical)."""
    path = os.path.join(repo_root, JITTER_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            val = data.get("observed_jitter_minutes")
            if isinstance(val, int) and val >= 0:
                return val
    except (OSError, ValueError):
        pass
    if period_minutes <= 0:
        return 0
    return min(15, math.ceil(period_minutes * 0.10))


def _next_tick_eta(repo_root: str, now: datetime.datetime):
    """Next rabbit-auto-evolve heartbeat fire as a single EXACT wall-clock
    string `HH:MM` — one bare timestamp, no range and no qualifier — or None on
    any absent/unreadable/unparseable/no-match condition (caller degrades to the
    bare idle line, no fabricated ETA). #844: mirrors contract Inv 55's cadence
    computation so the SessionStart banner and the Stop line agree.

    #881 (third reopen): the displayed minute is the next cron boundary PLUS the
    deterministic CronCreate jitter offset (Inv 56). CronCreate adds a
    deterministic per-job jitter to recurring tasks (up to 10% of the period
    late, capped at 15 min); on an idle session this is a stable constant
    (observed +13 for the 13,43 30-min heartbeat). The offset is read from the
    rabbit-auto-evolve-owned artifact tick-jitter.py persists.

    Reads the durable heartbeat cadence from
    `<repo_root>/.claude/scheduled_tasks.json` — the `tasks[]` entry whose
    `prompt` references rabbit-auto-evolve. Only the cron MINUTE field is
    matched against an unrestricted (`*`) HOUR, the shape the heartbeat uses
    (`13,43 * * * *`)."""
    path = os.path.join(repo_root, ".claude", "scheduled_tasks.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    cron = None
    for task in data.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        if "rabbit-auto-evolve" in str(task.get("prompt", "")):
            cron = task.get("cron")
            break
    if not isinstance(cron, str):
        return None
    parts = cron.split()
    if len(parts) < 1:
        return None
    minutes = _parse_cron_minutes(parts[0])
    if not minutes:
        return None
    candidate = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    for _ in range(1440):
        if candidate.minute in minutes:
            offset = _jitter_offset_minutes(repo_root, _period_minutes(minutes))
            fire = candidate + datetime.timedelta(minutes=offset)
            return fire.strftime("%H:%M")
        candidate += datetime.timedelta(minutes=1)
    return None


def _line2(repo_root: str) -> dict:
    aborted_path = os.path.join(repo_root, ABORTED_MARKER)
    if os.path.exists(aborted_path):
        reason = _read_marker_reason(aborted_path)
        base = "loop aborted on safety violation"
        if reason and reason != "session":
            text = f"{base} — {reason} — clear .rabbit-auto-evolve-aborted to resume"
        else:
            text = f"{base} — clear .rabbit-auto-evolve-aborted to resume"
        return {"text": text, "icon": "🛑", "color": "red"}

    restart_path = os.path.join(repo_root, RESTART_MARKER)
    if os.path.exists(restart_path):
        reason = _read_marker_reason(restart_path)
        base = "resume after restart: paste /rabbit-auto-evolve start"
        if reason and reason != "session":
            text = f"{base} (reason: {reason})"
        else:
            text = base
        return {"text": text, "icon": "🔁", "color": "yellow"}

    running_path = os.path.join(repo_root, RUNNING_MARKER)
    if os.path.exists(running_path):
        text = (
            "loop in progress — /rabbit-auto-evolve stop to halt, or wait "
            "for the current tick to complete"
        )
        return {"text": text, "icon": "🔄", "color": "yellow"}

    # #793: no priority marker — distinguish never-started (state file absent,
    # restart pending) from started-then-idle (state file present).
    if not os.path.isfile(os.path.join(repo_root, STATE_FILE)):
        return {"text": RESTART_PENDING_TEXT, "icon": "⏸", "color": "yellow"}

    # #844/#881: the started-then-idle line appends the next-tick ETA the Stop
    # line carries (contract Inv 55) for SessionStart<->Stop symmetry, as the
    # exact ", next tick HH:MM" suffix — a single wall-clock time, the next cron
    # boundary plus the deterministic CronCreate jitter offset (Inv 56), no
    # range and no qualifier. Honest degradation: the bare idle line when the
    # cadence source is absent/unparseable (no crash, no fabricated ETA).
    text = "paste: /rabbit-auto-evolve start"
    eta = _next_tick_eta(repo_root, _now())
    if eta is not None:
        text = f"{text}, next tick {eta}"
    return {
        "text": text,
        "icon": "▶",
        "color": "yellow",
    }


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "Inspect rabbit-auto-evolve runtime markers and emit the active "
            "banner JSON ({active, line1, line2}). Exit code is always 0."
        )
    ).parse_args()

    root = _repo_root()
    active_path = os.path.join(root, ACTIVE_MARKER)
    if not os.path.exists(active_path):
        print(json.dumps({"active": False, "line1": None, "line2": None}, indent=2))
        sys.exit(0)

    line1 = {
        "text": "AUTONOMOUS-EVOLVE MODE ACTIVE",
        "icon": "🤖",
        "color": "red",
    }
    line2 = _line2(root)
    print(
        json.dumps(
            {"active": True, "line1": line1, "line2": line2},
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
