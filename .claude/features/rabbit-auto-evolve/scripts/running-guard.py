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

A marker is STALE when EITHER:
  - its mtime is older than the MAX_TICK_DURATION window (default 1800 s;
    overridable via RABBIT_AUTO_EVOLVE_MAX_TICK_SECS for tests), OR
  - it records an owner `pid=<n>` AND that PID is not alive.

mtime is the PRIMARY staleness signal so the guard works even when the marker
carries no PID. start-loop.py writes `pid=<n> ts=<iso>` into the marker
content to enable the PID-liveness check; existence-based readers
(status-report.py, end-tick.py) are unaffected (they key on the filename).

  repo_root via RABBIT_AUTO_EVOLVE_REPO_ROOT, else os.getcwd().

Exit code is always 0 (the verdict is carried in `action`).

Version: 1.0.0
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
DEFAULT_MAX_TICK_SECS = 1800  # 30 min
_PID_RE = re.compile(r"pid=(\d+)")


def _repo_root():
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _max_tick_secs():
    raw = os.environ.get("RABBIT_AUTO_EVOLVE_MAX_TICK_SECS")
    if raw is None:
        return DEFAULT_MAX_TICK_SECS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_MAX_TICK_SECS


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


def _is_stale(path):
    """Return (stale, reason). mtime is the primary signal; a dead recorded
    PID is a secondary signal."""
    age = time.time() - os.path.getmtime(path)
    if age > _max_tick_secs():
        return True, f"mtime age {int(age)}s exceeds max-tick window"
    try:
        content = open(path).read()
    except OSError:
        content = ""
    m = _PID_RE.search(content)
    if m:
        pid = int(m.group(1))
        if not _pid_alive(pid):
            return True, f"owner pid {pid} not alive"
    return False, "fresh"


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
