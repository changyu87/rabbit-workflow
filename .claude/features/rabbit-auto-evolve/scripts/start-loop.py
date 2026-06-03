#!/usr/bin/env python3
"""start-loop.py — the explicit user `start` self-heal entry.

Usage:
  start-loop.py

Per spec.md Inv 19, `start` is an explicit "I want this to run" signal. This
script performs the two self-healing steps tied to that USER intent so the next
tick has a clean foothold:

  1. Cancel any pending stop. Delete `<repo_root>/.rabbit-auto-evolve-stop-requested`
     if present (idempotent). A stale stop marker from a previously-killed
     session would otherwise halt the loop at phase 0. This stop-cancel is the
     SOLE path that clears the stop marker (Inv 41): a MACHINE-fired `tick`
     invokes the shared phase-walk directly and NEVER runs this script, so a
     heartbeat can never resurrect a user-halted loop.
  2. Bootstrap state. If `<repo_root>/.rabbit/auto-evolve-state.json` does
     not exist, is empty, or fails JSON parse, write default content
     atomically (temp + os.rename, matching update-state.py's convention).
     A valid existing file is left untouched.

It does NOT write the `.rabbit-auto-evolve-running` marker. Per spec Inv 42
that write is owned by the shared phase-walk (`run-tick-phases.py`), which runs
the running-guard FIRST and writes the marker only after the guard returns
`proceed` — so neither the in-session nor the headless path false-skips on a
marker it itself wrote. The marker CONTENT shape (the DURABLE owner PID + an
ISO-8601 UTC timestamp `pid=<n> ts=<iso> session` for the Inv 35 running-guard)
is still defined here, in `_marker_content`, and imported by the phase-walk so
the content stays defined in ONE place. The recorded PID is the long-lived
session / tick-owner PID sourced from the Claude session environment
(`CLAUDE_SESSION_PID`, else the first non-shell ancestor walked up the PPID
chain) — NEVER a transient subprocess `os.getpid()`, which dies seconds after
the marker is written and would make the guard flag every tick stale. When no
durable owner can be determined, the PID is OMITTED (the content is
`ts=<iso> session`) and the guard relies on its activity signal alone (it
functions PID-free).

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Exit 0 on success; non-zero on self-heal error.

Version: 1.6.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import json
import os
import sys

STOP_MARKER = ".rabbit-auto-evolve-stop-requested"
STATE_DIR = ".rabbit"
STATE_FILE = "auto-evolve-state.json"
# The running marker content carries the DURABLE owner PID (when one can be
# determined) + an ISO-8601 UTC timestamp for the Inv 35 stale-marker
# running-guard, then the legacy `session` token (matching the
# set-evolve-mode.py marker convention so existing readers and prior
# content-shape expectations still see it).
CONTENT_SUFFIX = "session"
# Shells whose PID is too short-lived / non-owning to record as the durable
# tick owner; the PPID walk skips past these to a real ancestor.
_SHELL_NAMES = {"sh", "bash", "dash", "zsh", "tcsh", "csh", "fish", "ksh"}


def _proc_name(pid: int) -> str:
    """Best-effort process name for `pid` via /proc/<pid>/comm. Empty string
    when unreadable (the walk then treats it as a non-shell owner)."""
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip()
    except OSError:
        return ""


def _proc_ppid(pid):
    """Parent PID of `pid` via /proc/<pid>/stat (field 4), or None."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            data = f.read()
    except OSError:
        return None
    # The comm field (2nd) is parenthesized and may contain spaces; split on
    # the last ')' so positional fields after it are stable.
    rest = data.rpartition(")")[2].split()
    if len(rest) < 2:
        return None
    try:
        return int(rest[1])  # field 4 (ppid) is index 1 after state field.
    except ValueError:
        return None


def _durable_owner_pid():
    """Return the long-lived session / tick-owner PID, or None if none can be
    determined. Priority: CLAUDE_SESSION_PID env, else the first non-shell
    ancestor walked up the PPID chain from this process's parent. Never this
    process's own transient os.getpid()."""
    env_pid = os.environ.get("CLAUDE_SESSION_PID")
    if env_pid:
        try:
            pid = int(env_pid)
            if pid > 0:
                return pid
        except ValueError:
            pass
    pid = os.getppid()
    seen = set()
    while pid and pid > 1 and pid not in seen:
        seen.add(pid)
        name = _proc_name(pid)
        if name and name not in _SHELL_NAMES:
            return pid
        parent = _proc_ppid(pid)
        if parent is None:
            # Cannot walk further but this ancestor outlives the helper;
            # record it rather than dropping to PID-free.
            return pid
        pid = parent
    return None


def _marker_content() -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    owner = _durable_owner_pid()
    if owner is not None:
        return f"pid={owner} ts={now} {CONTENT_SUFFIX}"
    return f"ts={now} {CONTENT_SUFFIX}"


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _default_state() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "schema_version": "1.2.0",
        "updated_at": now,
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
        "pending_post_merge": [],
    }


def _cancel_pending_stop(repo_root: str) -> None:
    stop_path = os.path.join(repo_root, STOP_MARKER)
    if os.path.exists(stop_path):
        os.remove(stop_path)


def _bootstrap_state(repo_root: str) -> None:
    state_dir = os.path.join(repo_root, STATE_DIR)
    state_path = os.path.join(state_dir, STATE_FILE)
    needs_bootstrap = False
    if not os.path.exists(state_path):
        needs_bootstrap = True
    else:
        try:
            with open(state_path) as f:
                json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            needs_bootstrap = True
    if not needs_bootstrap:
        return
    os.makedirs(state_dir, exist_ok=True)
    tmp_path = state_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(_default_state(), f, indent=2)
    os.rename(tmp_path, state_path)


def main() -> None:
    argparse.ArgumentParser(
        description="Explicit user `start` self-heal: cancel a pending stop "
                    "and bootstrap the state file (the running marker is "
                    "written by the shared phase-walk, Inv 42)."
    ).parse_args()
    root = _repo_root()
    try:
        _cancel_pending_stop(root)
        _bootstrap_state(root)
    except OSError as e:
        sys.stderr.write(f"start-loop: self-heal failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
