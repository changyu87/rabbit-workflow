#!/usr/bin/env python3
"""detect-scheduler.py — detect the available tick scheduler mechanism.

Usage:
  detect-scheduler.py        # emit {"scheduler": ..., "reason": ...} on stdout

Per rabbit-auto-evolve spec.md Inv 34 (D2, issue #521), the auto-evolve loop
schedules ticks via the system `crontab` WHERE AVAILABLE, and falls back to a
durable `CronCreate` heartbeat on hosts where crontab is administratively
blocked. This script performs the DETERMINISTIC detection half of that
decision (a script cannot call `CronCreate` — that is the dispatcher's tool
action); it only reports which mechanism applies.

It probes `crontab -l` via the `RABBIT_CRONTAB_CMD` env override when set
(so tests can inject a fake shim, the same pattern as install-cron.py), else
the literal `crontab`. It distinguishes:

  - USABLE      — the probe exits 0, OR exits non-zero WITHOUT a permission
                  denial (the legitimate "no crontab for user" empty case).
                  Emits {"scheduler": "crontab", ...}.
  - RESTRICTED  — the probe fails with a permission denial ("not allowed")
                  in stderr. Emits {"scheduler": "croncreate", ...}.

Exit code is always 0 (the verdict is carried in the `scheduler` field).

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys

# A restricted-crontab denial is recognised by this phrase in the binary's
# stderr — the standard message is "You (<user>) are not allowed to use this
# program (crontab)". The legitimate empty case ("no crontab for <user>")
# does NOT contain it. Mirrors install-cron.py's _RESTRICTED_SIGNAL.
_RESTRICTED_SIGNAL = "not allowed"


def _crontab_cmd():
    return os.environ.get("RABBIT_CRONTAB_CMD", "crontab")


def detect():
    """Return (scheduler, reason). `scheduler` is "crontab" or "croncreate"."""
    try:
        proc = subprocess.run(
            [_crontab_cmd(), "-l"],
            capture_output=True, text=True,
        )
    except OSError as e:
        # The crontab binary is missing/unrunnable — treat as restricted so
        # the loop still schedules via the CronCreate fallback.
        return "croncreate", f"crontab binary unavailable: {e}"

    if proc.returncode == 0:
        return "crontab", "crontab usable"
    if _RESTRICTED_SIGNAL in (proc.stderr or "").lower():
        return "croncreate", "crontab restricted (permission denied)"
    # Non-zero without a permission denial is the legitimate "no crontab for
    # user" empty case — crontab is usable, the user just has no entries yet.
    return "crontab", "no crontab for user (empty, crontab usable)"


def main():
    argparse.ArgumentParser(
        description="Detect the available tick scheduler (crontab where "
                    "usable, croncreate fallback where restricted); emit "
                    "JSON {scheduler, reason} on stdout (Inv 34 / #521)."
    ).parse_args()
    scheduler, reason = detect()
    json.dump({"scheduler": scheduler, "reason": reason}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
