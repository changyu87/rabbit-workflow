#!/usr/bin/env python3
"""start-loop.py — self-heal then write the .rabbit-auto-evolve-running marker.

Usage:
  start-loop.py

Per rabbit-auto-evolve spec.md Inv 17, all rabbit-auto-evolve runtime-marker
writes go through scripts so scope-guard (which inspects literal Bash command
strings) does not block them. This script wraps the `start` subcommand's
marker write inside a Python process.

Per spec.md Inv 19 (added in v0.7.2 for issue #373), `start` is an explicit
"I want this to run" signal — before writing the running marker it performs
two self-healing steps so the next tick has a clean foothold:

  1. Cancel any pending stop. Delete `<repo_root>/.rabbit-auto-evolve-stop-requested`
     if present (idempotent). A stale stop marker from a previously-killed
     session would otherwise halt the loop at phase 0.
  2. Bootstrap state. If `<repo_root>/.rabbit/auto-evolve-state.json` does
     not exist, is empty, or fails JSON parse, write default content
     atomically (temp + os.rename, matching update-state.py's convention).
     A valid existing file is left untouched.

Then writes `<repo_root>/.rabbit-auto-evolve-running` with the literal
content `session` (matching the set-evolve-mode.py marker convention).
Idempotent: re-running with the marker already at the same content is a
clean no-op.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Exit 0 on success; non-zero on write error.

Version: 1.2.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import json
import os
import sys

MARKER = ".rabbit-auto-evolve-running"
STOP_MARKER = ".rabbit-auto-evolve-stop-requested"
STATE_DIR = ".rabbit"
STATE_FILE = "auto-evolve-state.json"
CONTENT = "session"


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _default_state() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "schema_version": "1.1.0",
        "updated_at": now,
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
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
        description="Self-heal then write the .rabbit-auto-evolve-running marker."
    ).parse_args()
    root = _repo_root()
    try:
        _cancel_pending_stop(root)
        _bootstrap_state(root)
        path = os.path.join(root, MARKER)
        with open(path, "w") as f:
            f.write(CONTENT)
    except OSError as e:
        sys.stderr.write(f"start-loop: write failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
