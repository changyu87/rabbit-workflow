#!/usr/bin/env python3
"""install-cron.py — install the system-cron entry that fires the headless tick.

Usage:
  install-cron.py            # idempotently install the tick-headless crontab entry

Per rabbit-auto-evolve spec.md Inv 32 (issue #414), the system cron is the
SOLE tick scheduler — the prior self-chained `ScheduleWakeup` was removed
entirely. This script installs ONE crontab entry of the form:

  */30 * * * * cd <repo_root> && python3
    .claude/features/rabbit-auto-evolve/scripts/tick-headless.py
    >> .rabbit/tick-headless.log 2>&1

using the `crontab -l` (read current) + append + `crontab -` (write back)
pattern. It is IDEMPOTENT: if an entry mentioning `tick-headless.py` already
exists in the user's crontab, this is a clean no-op (running twice yields
exactly one entry). Unrelated crontab lines are preserved verbatim.

`set-evolve-mode.py on` invokes this script after writing the three
activation markers.

The `crontab` binary is resolved via the `RABBIT_CRONTAB_CMD` env var when
set (so tests can inject a fake shim), else the literal `crontab`. The repo
root is resolved via `RABBIT_AUTO_EVOLVE_REPO_ROOT` when set, else
`os.getcwd()`.

Exit code: 0 on success (including the idempotent no-op). Non-zero only on a
genuine crontab read/write failure.

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
TICK_SCRIPT = ".claude/features/rabbit-auto-evolve/scripts/tick-headless.py"
LOG_PATH = ".rabbit/tick-headless.log"
SCHEDULE = "*/30 * * * *"


def _crontab_cmd():
    return os.environ.get("RABBIT_CRONTAB_CMD", "crontab")


def _repo_root():
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT", os.getcwd())


def _entry_line(repo_root):
    return (
        f"{SCHEDULE} cd {repo_root} && python3 {TICK_SCRIPT} "
        f">> {LOG_PATH} 2>&1"
    )


def _read_crontab():
    """Return the current crontab text, or '' when the user has no crontab.

    `crontab -l` exits non-zero (typically 1) with a "no crontab for <user>"
    message when no crontab exists — that is the legitimate empty case, NOT
    an error, so we treat any non-zero exit as an empty crontab.
    """
    proc = subprocess.run(
        [_crontab_cmd(), "-l"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def _write_crontab(text):
    """Replace the crontab with `text` via `crontab -`. Returns True on
    success."""
    proc = subprocess.run(
        [_crontab_cmd(), "-"],
        input=text, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(
            f"install-cron: `crontab -` failed (exit {proc.returncode}): "
            f"{proc.stderr}\n"
        )
        return False
    return True


def install():
    repo_root = _repo_root()
    current = _read_crontab()

    # Idempotency: an entry mentioning tick-headless.py already present is a
    # clean no-op.
    if ENTRY_TOKEN in current:
        print("install-cron: tick-headless entry already present — no-op")
        return 0

    entry = _entry_line(repo_root)
    # Preserve existing lines; append the new entry with a trailing newline.
    if current and not current.endswith("\n"):
        current += "\n"
    new_crontab = current + entry + "\n"

    if not _write_crontab(new_crontab):
        return 1
    print(f"install-cron: installed tick-headless entry: {entry}")
    return 0


def main():
    argparse.ArgumentParser(
        description="Idempotently install the system-cron entry that fires "
                    "the rabbit-auto-evolve headless tick (Inv 32 / #414)."
    ).parse_args()
    return install()


if __name__ == "__main__":
    sys.exit(main())
