#!/usr/bin/env python3
"""tick-headless.py — the headless (Claude-free) tick fired by the system cron.

Usage:
  tick-headless.py           # run one headless tick

Per rabbit-auto-evolve spec.md Inv 32 (issue #414), the system cron is the
SOLE tick scheduler — the self-chained `ScheduleWakeup` was removed entirely.
A live Claude session is required only for phase 5 (`dispatch`); every other
tick phase is deterministic and runs here without Claude. The cron entry
(installed by `install-cron.py`) invokes this script on a fixed cadence.

Phases walked (the Claude-free subset of the 12-phase session tick):

  - phase 0  stop-check    — short-circuit to a clean no-op if
                             `.rabbit-auto-evolve-stop-requested` exists.
  - phase 1  restart-check — also short-circuit on
                             `.rabbit-auto-evolve-aborted` (a halted loop).
  - running-guard          — the heartbeat "is a tick running?" check invokes
                             `running-guard.py` (Inv 35 / #526), NOT a bare
                             marker-presence test: a STALE marker is cleared so
                             a crashed tick never wedges the loop, while a FRESH
                             (active) tick yields a clean no-op so this headless
                             tick never runs concurrently on top of it.
  - phases 2-4 fetch|triage|plan — the canonical
                             `fetch-queue.py | triage-batch.py | plan-batch.py`
                             pipe (Inv 18).
  - phase 5  dispatch      — SKIPPED. Dispatching a TDD subagent requires a
                             Claude session; the headless tick never runs it.
  - phase 6  merge         — `merge-prs.py --record-pending <ready-PRs>` for
                             the PRs listed in the state's `merge_ready` field.
                             Skipped when there are no ready PRs.
  - phases 7-9 post-merge  — `run-post-merge.py` drains `pending_post_merge`
                             (release -> cleanup -> catch-up). Clean no-op
                             when empty.
  - phase 10 persist       — `update-state.py` writes the state file.
  - phase 11 schedule      — NO-OP. The cron fires the next tick; no
                             `ScheduleWakeup` / `CronCreate` is used.

Resolution (matching the sibling scripts):
  - sibling scripts via `RABBIT_AUTO_EVOLVE_SCRIPT_DIR`, else this script's dir.
  - repo root (for marker existence checks) via `RABBIT_AUTO_EVOLVE_REPO_ROOT`,
    else `os.getcwd()`.
  - state dir via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else `<cwd>/.rabbit`.

A single JSON result object is emitted on stdout summarizing which phases ran.
`dispatch` is always marked `"skipped"` (no Claude). Exit code is 0 on a
completed tick (including every short-circuit no-op); non-zero on an
unexpected phase-script failure that should surface in the cron log.

Version: 1.1.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys

STOP_MARKER = ".rabbit-auto-evolve-stop-requested"
ABORT_MARKER = ".rabbit-auto-evolve-aborted"


def _script_dir():
    return os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
                          os.path.dirname(os.path.abspath(__file__)))


def _repo_root():
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT", os.getcwd())


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _state_path():
    return os.path.join(_state_dir(), "auto-evolve-state.json")


def _read_state():
    try:
        with open(_state_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _merge_ready():
    """Return the list of PR numbers ready to merge from the state's
    `merge_ready` field. Empty list when missing/malformed."""
    state = _read_state()
    ready = state.get("merge_ready")
    if not isinstance(ready, list):
        return []
    return [n for n in ready if isinstance(n, int) and not isinstance(n, bool)]


def _run(script_name, args, stdin_text=None):
    """Invoke a sibling phase script. Returns its CompletedProcess. Phase
    stderr is passed through (so the cron log carries diagnostics); stdout is
    returned for piping/capture."""
    script = os.path.join(_script_dir(), script_name)
    proc = subprocess.run(
        [sys.executable, script, *args],
        input=stdin_text,
        capture_output=True, text=True,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc


def run():
    repo_root = _repo_root()
    result = {"status": "completed", "phases": {}, "dispatch": "skipped"}

    # --- phase 0 / 1: stop / abort short-circuit --------------------------
    if os.path.exists(os.path.join(repo_root, STOP_MARKER)):
        result["status"] = "noop"
        result["reason"] = "stop-requested"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if os.path.exists(os.path.join(repo_root, ABORT_MARKER)):
        result["status"] = "noop"
        result["reason"] = "aborted"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    # --- running-guard: heartbeat "is a tick running?" (Inv 35 / #526) -----
    # Invoke the staleness-aware guard, NOT a bare marker-presence test: a
    # crashed tick's STALE marker is cleared (we then proceed); a FRESH/active
    # tick yields a clean no-op so we never run on top of it.
    guard = _run("running-guard.py", [])
    try:
        verdict = json.loads(guard.stdout)
    except (ValueError, AttributeError):
        verdict = {}
    if verdict.get("action") == "skip":
        result["status"] = "noop"
        result["reason"] = "tick-running"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if verdict.get("stale_cleared"):
        result["running_guard"] = "stale-cleared"

    # --- phases 2-4: fetch | triage | plan --------------------------------
    fetch = _run("fetch-queue.py", [])
    result["phases"]["fetch"] = fetch.returncode
    if fetch.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "fetch-failed"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    triage = _run("triage-batch.py", [], stdin_text=fetch.stdout)
    result["phases"]["triage"] = triage.returncode
    if triage.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "triage-failed"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    plan = _run("plan-batch.py", ["--max-parallel", "4"], stdin_text=triage.stdout)
    result["phases"]["plan"] = plan.returncode
    if plan.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "plan-failed"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    # --- phase 6: merge ready PRs -----------------------------------------
    ready = _merge_ready()
    if ready:
        pr_list = ",".join(str(n) for n in ready)
        merge = _run("merge-prs.py", [pr_list, "--record-pending"])
        result["phases"]["merge"] = merge.returncode
        if merge.returncode != 0:
            result["status"] = "failed"
            result["reason"] = "merge-failed"
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 1
    else:
        result["phases"]["merge"] = "skipped-no-ready-prs"

    # --- phases 7-9: post-merge drain (release -> cleanup -> catch-up) -----
    post = _run("run-post-merge.py", [])
    result["phases"]["post_merge"] = post.returncode
    if post.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "post-merge-failed"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    # --- phase 10: persist -------------------------------------------------
    # Re-read the (possibly mutated by merge/post-merge) state and write it
    # back through update-state.py so the canonical persist path runs.
    # `merge_ready` is a transient per-tick hint (not part of the canonical
    # Inv 9 state schema), so drop it before handing the object to
    # update-state.py, whose validator rejects unknown keys.
    state = _read_state()
    state.pop("merge_ready", None)
    persist = _run("update-state.py", [], stdin_text=json.dumps(state))
    result["phases"]["persist"] = persist.returncode
    if persist.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "persist-failed"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    # --- phase 11: schedule -> NO-OP (cron owns scheduling) ---------------
    result["schedule"] = "cron-owned-noop"

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main():
    argparse.ArgumentParser(
        description="Run one headless (Claude-free) rabbit-auto-evolve tick: "
                    "phases 0-1, 2-4, 6, 7-9, 10. Phase 5 (dispatch) is "
                    "skipped (needs Claude); phase 11 (schedule) is a no-op "
                    "(the system cron owns scheduling, Inv 32 / #414)."
    ).parse_args()
    return run()


if __name__ == "__main__":
    sys.exit(main())
