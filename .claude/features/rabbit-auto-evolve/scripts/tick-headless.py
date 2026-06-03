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

The deterministic phase-walk itself lives in ONE shared place,
`run-tick-phases.py` (Inv 40 / #513): the headless tick chains its
`pre-dispatch` segment -> (skip dispatch, no Claude) -> `post-dispatch`
segment. The in-session tick walks the SAME two segments and differs ONLY by
inserting Phase 5 (dispatch) between them. This module owns no phase logic of
its own beyond the headless-specific "skip dispatch, schedule is a cron-owned
no-op" framing.

Version: 2.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import importlib.util
import json
import os
import sys


def _load_phase_walk():
    """Import the shared phase-walk module (hyphenated filename, so load by
    path). Resolved next to this script, or via RABBIT_AUTO_EVOLVE_SCRIPT_DIR
    (so the test harness's stub-script dir is honored consistently with the
    sibling phase scripts)."""
    script_dir = os.environ.get(
        "RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
        os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(script_dir, "run-tick-phases.py")
    if not os.path.isfile(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "run-tick-phases.py")
    spec = importlib.util.spec_from_file_location("run_tick_phases", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run():
    walk = _load_phase_walk()
    result = {"status": "completed", "phases": {}, "dispatch": "skipped"}

    # --- pre-dispatch segment (sync, stop/abort, running-guard, 2-4) -------
    pre, code = walk.run_pre_dispatch()
    result["phases"].update(pre.get("phases", {}))
    if "running_guard" in pre:
        result["running_guard"] = pre["running_guard"]
    if pre.get("action") == "skip":
        # A clean short-circuit (sync-fail / stop / abort / tick-running) or a
        # phase-2-4 failure. Mirror the segment's status/reason and exit code.
        result["status"] = pre.get("status", "noop")
        if "reason" in pre:
            result["reason"] = pre["reason"]
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return code

    # --- phase 5: dispatch -> SKIPPED (no Claude in the headless tick) -----

    # --- post-dispatch segment (merge, post-merge, persist) ---------------
    post, code = walk.run_post_dispatch()
    result["phases"].update(post.get("phases", {}))
    if post.get("status") == "failed":
        result["status"] = "failed"
        if "reason" in post:
            result["reason"] = post["reason"]
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return code

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
