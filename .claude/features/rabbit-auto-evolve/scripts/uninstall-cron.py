#!/usr/bin/env python3
"""uninstall-cron.py — remove the system-cron entry that fires the headless tick.

Usage:
  uninstall-cron.py          # idempotently remove the tick-headless crontab entry

Per rabbit-auto-evolve spec.md Inv 32 (issue #414), the system cron is the
SOLE tick scheduler. This script removes the entry installed by
install-cron.py using the `crontab -l | grep -v tick-headless | crontab -`
pattern (implemented in Python so it depends on no shell). It is IDEMPOTENT
and a safe no-op when the entry is absent (and when the user has no crontab
at all). Unrelated crontab lines are preserved verbatim.

`set-evolve-mode.py off` invokes this script before tearing down the
activation markers.

The `crontab` binary is resolved via the `RABBIT_CRONTAB_CMD` env var when
set (so tests can inject a fake shim), else the literal `crontab`.

Exit code: 0 on success (including the absent / no-crontab no-op). Non-zero
only on a genuine crontab write failure.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import os
import subprocess
import sys

ENTRY_TOKEN = "tick-headless.py"


def _crontab_cmd():
    return os.environ.get("RABBIT_CRONTAB_CMD", "crontab")


def _read_crontab():
    """Return the current crontab text, or None when the user has no crontab
    (so the caller can short-circuit the absent case without a needless
    write)."""
    proc = subprocess.run(
        [_crontab_cmd(), "-l"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _write_crontab(text):
    proc = subprocess.run(
        [_crontab_cmd(), "-"],
        input=text, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(
            f"uninstall-cron: `crontab -` failed (exit {proc.returncode}): "
            f"{proc.stderr}\n"
        )
        return False
    return True


def uninstall():
    current = _read_crontab()
    if current is None:
        # No crontab at all — nothing to remove.
        print("uninstall-cron: no crontab present — no-op")
        return 0

    if ENTRY_TOKEN not in current:
        print("uninstall-cron: no tick-headless entry present — no-op")
        return 0

    # Drop every line mentioning the tick-headless entry (the grep -v pattern).
    kept = [
        line for line in current.splitlines()
        if ENTRY_TOKEN not in line
    ]
    new_crontab = "\n".join(kept)
    if new_crontab:
        new_crontab += "\n"

    if not _write_crontab(new_crontab):
        return 1
    print("uninstall-cron: removed tick-headless entry")
    return 0


def main():
    argparse.ArgumentParser(
        description="Idempotently remove the system-cron entry that fires "
                    "the rabbit-auto-evolve headless tick (Inv 32 / #414)."
    ).parse_args()
    return uninstall()


if __name__ == "__main__":
    sys.exit(main())
