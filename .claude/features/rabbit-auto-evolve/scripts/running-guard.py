#!/usr/bin/env python3
"""running-guard.py — clear STALE running markers so the loop never wedges.

Usage:
  running-guard.py           # inspect the running marker, emit proceed/skip

Per rabbit-auto-evolve spec.md Inv 35 (D3, issue #521), before a session
enters a tick (and at every heartbeat) the loop must distinguish a tick that
is genuinely running from a wedged/dead one. Without this a crashed tick
leaves `.rabbit-auto-evolve-running` behind and the loop skips forever — the
silent-stall class #414 set out to eliminate.

This script inspects `<repo_root>/.rabbit-auto-evolve-running` and emits JSON:

  - absent              -> {"action": "proceed", "running": false}
  - present + STALE     -> clears the marker, logs "stale marker cleared" via
                           tick-log.py, and returns
                           {"action": "proceed", "running": true,
                            "stale_cleared": true}
  - present + FRESH     -> {"action": "skip", "reason": "tick-running"}

STALENESS (Inv 35, corrected for issue #526). The old "stale when marker mtime
> MAX_TICK_DURATION OR the recorded PID is dead" rule was UNSOUND: the marker's
mtime is frozen at creation, so a long-but-active tick tripped the age window;
and start-loop.py stamped its own transient `os.getpid()`, which dies seconds
after the marker is written, so the dead-PID arm flagged EVERY tick stale.
Either false-stale verdict clears an ACTIVE tick's marker and lets a concurrent
tick start on top of it — corrupting the shared state the guard protects.

The corrected rule keys on ACTUAL activity and a DURABLE owner, combined
CONSERVATIVELY (prefer a false-NEGATIVE over a false-POSITIVE):

  - Activity signal (PRIMARY): the tick is ACTIVE when
    `<state_dir>/auto-evolve-state.json` exists AND its mtime advanced within
    IDLE_WINDOW (default 600 s; overridable via RABBIT_AUTO_EVOLVE_IDLE_SECS).
    state.json mtime advances on every update-state.py write, so it tracks
    liveness even for a multi-hour active tick. Total elapsed since marker
    creation is NO LONGER a staleness signal on its own.
  - Durable owner liveness (SECONDARY): when the marker records an owner
    `pid=<n>` AND that process is alive, the tick is ACTIVE regardless of the
    activity window. When no PID is recorded, the guard relies on the activity
    signal alone (it MUST still function PID-free).
  - Conservative AND-combine: STALE iff (no live owner) AND (state.json idle
    beyond IDLE_WINDOW, or absent). If EITHER the owner is alive OR activity is
    recent, the marker is FRESH and preserved.

The marker records a DURABLE owner `pid=<n>` (the long-lived session PID, not
the writer's transient subprocess PID) and an ISO-8601 timestamp in its content
— built by start-loop.py's `_marker_content` and written by the shared
phase-walk after this guard returns proceed (Inv 42). Existence-based readers
(status-report.py, end-tick.py) are unaffected (they key on the filename, which
is unchanged).

  repo_root via RABBIT_AUTO_EVOLVE_REPO_ROOT, else os.getcwd().
  state_dir via RABBIT_AUTO_EVOLVE_STATE_DIR, else <cwd>/.rabbit
  (matching update-state.py).

MAX_TICK_DURATION / RABBIT_AUTO_EVOLVE_MAX_TICK_SECS is kept readable for
back-compat but it MUST NOT alone force stale — only the IDLE_WINDOW activity
test governs the time arm.

Exit code is always 0 (the verdict is carried in `action`).

Version: 1.1.1
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import re
import sys
import time

MARKER = ".rabbit-auto-evolve-running"
STATE_FILE = "auto-evolve-state.json"
DEFAULT_MAX_TICK_SECS = 1800  # 30 min — retained for back-compat (not a
                              # standalone staleness signal post-#526).
DEFAULT_IDLE_SECS = 600  # 10 min — the activity window (Inv 35 / #526).
_PID_RE = re.compile(r"pid=(\d+)")


def _repo_root():
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _state_path():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    state_dir = override if override else os.path.join(os.getcwd(), ".rabbit")
    return os.path.join(state_dir, STATE_FILE)


def _idle_secs():
    raw = os.environ.get("RABBIT_AUTO_EVOLVE_IDLE_SECS")
    if raw is None:
        return DEFAULT_IDLE_SECS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_IDLE_SECS


def _pid_alive(pid):
    """True if a process with `pid` exists. os.kill(pid, 0) raises
    ProcessLookupError when absent, PermissionError when alive but
    unsignalable (still alive)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _owner_alive(path):
    """True iff the marker records a `pid=<n>` AND that process is alive.
    A PID-free marker yields False (no live owner — fall back to activity)."""
    try:
        content = open(path).read()
    except OSError:
        return False
    m = _PID_RE.search(content)
    if not m:
        return False
    return _pid_alive(int(m.group(1)))


def _active_recent():
    """True iff state.json exists AND its mtime advanced within IDLE_WINDOW.
    Tracks the LIVE tick's activity (every update-state.py write touches it),
    so a long-but-active tick is never judged idle."""
    state_path = _state_path()
    try:
        age = time.time() - os.path.getmtime(state_path)
    except OSError:
        return False  # absent state.json -> no activity signal
    return age <= _idle_secs()


def _is_stale(path):
    """Return (stale, reason). STALE only when BOTH no-live-owner AND
    state.json idle (conservative AND; prefer false-negative). Either a live
    owner OR recent activity keeps the marker FRESH (Inv 35 / #526)."""
    if _owner_alive(path):
        return False, "owner pid alive"
    if _active_recent():
        return False, "state.json activity within idle window"
    return True, "no live owner and state.json idle"


def _log(decision, detail):
    """Append a decision line via tick-log.py's in-process append (best
    effort — a logging failure must not change the guard verdict).
    tick-log.py has a hyphen in its name, so it is loaded by file spec."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        import importlib.util  # noqa: PLC0415
        spec = importlib.util.spec_from_file_location(
            "tick_log", os.path.join(here, "tick-log.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.append(decision, detail)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"running-guard: tick-log append failed: {e}\n")


def guard():
    path = os.path.join(_repo_root(), MARKER)
    if not os.path.exists(path):
        return {"action": "proceed", "running": False}

    stale, reason = _is_stale(path)
    if stale:
        try:
            os.remove(path)
        except OSError as e:
            sys.stderr.write(f"running-guard: could not clear marker: {e}\n")
        _log("stale marker cleared", reason)
        return {"action": "proceed", "running": True, "stale_cleared": True}

    return {"action": "skip", "reason": "tick-running"}


def main():
    argparse.ArgumentParser(
        description="Inspect the running marker; clear a STALE one and log "
                    "it, else proceed/skip (Inv 35 / D3 / #521)."
    ).parse_args()
    json.dump(guard(), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
