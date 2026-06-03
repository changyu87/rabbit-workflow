#!/usr/bin/env python3
"""schedule-check.py — validate the ScheduleWakeup parameters BEFORE the
tick's phase 11 (`schedule`) emits the harness call.

Usage:
  schedule-check.py --delay-seconds N --prompt "<str>" --reason "<str>"

`ScheduleWakeup` is a Claude Code harness feature, not a Python function,
so this script does NOT call it — it validates the LOGIC that determines
the call's parameters and exits non-zero if any parameter would make the
harness silently drop the wakeup. Issue #409: the auto-evolve loop
silently stopped scheduling (a 5h+ gap with no tick, no error, no log
line) because SKILL.md's phase-11 documentation pinned no concrete
parameters; an out-of-range delay or a prompt that does not re-enter the
tick produces exactly this silent stall. The tick invokes this validator
immediately before emitting the call so a bad parameter fails loudly
(non-zero exit + a JSON error payload) instead of silently halting the
loop.

Validity rules (spec.md Inv 29):
  - 60 <= delay_seconds <= 3600 — the harness ignores a 0/negative delay,
    and an over-long delay is indistinguishable from a hang. Per spec
    Inv 31 (issue #412) the schedule phase selects 60 (queue non-empty —
    refire immediately) or 3600 (queue empty — hourly idle check); BOTH
    are inside this band, so this validator accepts either.
  - prompt is non-empty AND re-invokes the tick: it MUST contain the
    literal substring `/rabbit-auto-evolve tick`.
  - reason is non-empty (a human-readable why-this-wakeup string).

Output (stdout, JSON object):
  - all valid → {"ok": true, "delay_seconds": N, "prompt": "...",
    "reason": "..."}; exit 0.
  - any violation → {"ok": false, "errors": ["...", ...]}; exit 1.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import sys

DELAY_MIN = 60
DELAY_MAX = 3600
REINVOKE_TOKEN = "/rabbit-auto-evolve tick"


def validate(delay_seconds, prompt, reason):
    """Return a list of human-readable violation strings (empty == valid)."""
    errors = []

    if delay_seconds < DELAY_MIN or delay_seconds > DELAY_MAX:
        errors.append(
            f"delay_seconds {delay_seconds} out of range "
            f"[{DELAY_MIN}, {DELAY_MAX}] — the harness ignores a "
            f"0/negative delay and an over-long delay looks like a hang"
        )

    if not prompt or not prompt.strip():
        errors.append("prompt is empty — the wakeup would not re-enter the tick")
    elif REINVOKE_TOKEN not in prompt:
        errors.append(
            f"prompt does not re-invoke the tick "
            f"(missing literal substring {REINVOKE_TOKEN!r})"
        )

    if not reason or not reason.strip():
        errors.append("reason is empty — a wakeup must carry a non-empty reason")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Validate ScheduleWakeup parameters before the auto-evolve "
            "schedule phase emits the harness call (issue #409)."
        )
    )
    parser.add_argument(
        "--delay-seconds",
        type=int,
        required=True,
        help=f"wakeup delay in seconds (must be {DELAY_MIN}..{DELAY_MAX})",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help=f"the re-invoke prompt (must contain {REINVOKE_TOKEN!r})",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="non-empty human-readable reason for the wakeup",
    )
    args = parser.parse_args()

    errors = validate(args.delay_seconds, args.prompt, args.reason)

    if errors:
        json.dump({"ok": False, "errors": errors}, sys.stdout)
        sys.stdout.write("\n")
        sys.exit(1)

    json.dump(
        {
            "ok": True,
            "delay_seconds": args.delay_seconds,
            "prompt": args.prompt,
            "reason": args.reason,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
