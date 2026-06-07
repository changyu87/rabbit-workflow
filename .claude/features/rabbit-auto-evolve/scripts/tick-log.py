#!/usr/bin/env python3
"""tick-log.py — minimal append-only structured logger for tick decisions.

Usage:
  tick-log.py --decision <decision> [--detail <detail>]

Per rabbit-auto-evolve spec.md Inv 36 (D4, issue #521), every heartbeat /
running-guard / schedule decision is logged so the loop's behaviour is
observable (the silent-stall failure mode #414 set out to eliminate). This is
the MINIMAL logger: it appends ONE JSON object per line
(`{ts, decision, detail}`) to `<state_dir>/tick.log`.

  state_dir defaults to <cwd>/.rabbit
  state_dir is overridable via RABBIT_AUTO_EVOLVE_STATE_DIR (matching
  update-state.py's resolution).

`ts` is an ISO-8601 UTC timestamp. The decisions callers append include
`entering`, `skipped: tick already running`, `idle: no work`, and
`stale marker cleared`.

NOTE: the full configurable on/off + verbosity logger is the scope of issue
#404 and is intentionally NOT implemented here — this is the narrow append
primitive `running-guard.py` (D3) and `schedule-decision.py` (D1) need.

It also exposes `append(decision, detail)` for in-process callers (sibling
scripts import it rather than re-deriving the log path).

Exit 0 on success; non-zero on write error.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import json
import os
import sys

LOG_NAME = "tick.log"


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def append(decision, detail=""):
    """Append one {ts, decision, detail} JSON line to <state_dir>/tick.log.
    Creates the state dir if needed. Returns the log path."""
    state_dir = _state_dir()
    os.makedirs(state_dir, exist_ok=True)
    log_path = os.path.join(state_dir, LOG_NAME)
    record = {"ts": _now_iso(), "decision": decision, "detail": detail or ""}
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    return log_path


def main():
    parser = argparse.ArgumentParser(
        description="Append one structured JSON tick-decision line to "
                    ".rabbit/tick.log (Inv 36 / D4 / #521). Honors "
                    "RABBIT_AUTO_EVOLVE_STATE_DIR."
    )
    parser.add_argument("--decision", required=True,
                        help="the decision token (e.g. 'idle: no work')")
    parser.add_argument("--detail", default="",
                        help="optional free-form detail string")
    args = parser.parse_args()
    try:
        append(args.decision, args.detail)
    except OSError as e:
        sys.stderr.write(f"tick-log: write failed: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
