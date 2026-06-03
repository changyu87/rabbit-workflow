#!/usr/bin/env python3
"""run-post-merge.py — deterministic, non-skippable runner for tick phases 7-9.

Usage:
  run-post-merge.py

Per rabbit-auto-evolve spec.md Inv 30 (issue #499), tick phases 7 (release),
8 (cleanup), and 9 (catch-up) were prose in SKILL.md walked by the LLM
orchestrator. After phase 6 (merge) landed a large batch of PRs, the
orchestrator ended the tick for scale/context reasons and phases 7-9 were
silently dropped — the same class of failure as the LLM-walked-prose skips
in #405 / #409 / #439. This script owns the phase-7-through-9 sequencing so
the steps are deterministic and non-skippable.

It:
  1. Reads `pending_post_merge` (array of merged PR numbers owed post-merge
     processing) from `<state_dir>/auto-evolve-state.json`.
  2. If empty / missing / malformed → CLEAN NO-OP: emit
     {"status": "noop", "pending": []} and exit 0 (no phase script invoked).
  3. Otherwise, in order:
       - Phase 7 (release):  `release-bump.py <pr#>` once per PR.
       - Phase 8 (cleanup):  `cleanup-branches.py <comma-joined pr-list>` once.
       - Phase 9 (catch-up): `classify-merge-restart.py <pr#>` once per PR.
  4. On completion (all phase scripts exited 0 AND every release-bump.py
     reported status "released"), clears `pending_post_merge` to [] in the
     state file (atomic via temp+rename).
  5. Emits a result JSON object on stdout recording the pending set and each
     phase's outcome.

Exit code: 0 on success (including the no-op path). Non-zero on any phase
failure — a phase script exiting non-zero OR a release-bump.py whose stdout
JSON status is not "released" (skipped/failed/unparseable; release-bump.py
exits 0 even when it skips, issue #512) — the caller (end-tick.py / the SKILL
schedule phase) sees a loud, locatable failure instead of a silently-dropped
phase. On a phase failure `pending_post_merge` is NOT cleared, so the next
tick's tick-start drain retries the owed work.

The sibling phase scripts (release-bump.py, cleanup-branches.py,
classify-merge-restart.py) are resolved via the RABBIT_AUTO_EVOLVE_SCRIPT_DIR
env var when set, else this script's own dirname (matching merge-prs.py /
release-bump.py / cleanup-branches.py). The state dir resolves via
RABBIT_AUTO_EVOLVE_STATE_DIR when set, else `<cwd>/.rabbit` (matching
update-state.py).

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


def _script_dir():
    return os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR",
                          os.path.dirname(os.path.abspath(__file__)))


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _state_path():
    return os.path.join(_state_dir(), "auto-evolve-state.json")


def _read_pending():
    """Return the pending_post_merge list, or [] when the state file is
    missing / malformed / the field is absent (the clean-no-op case)."""
    try:
        with open(_state_path()) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return []
    pending = state.get("pending_post_merge")
    if not isinstance(pending, list):
        return []
    return [n for n in pending if isinstance(n, int) and not isinstance(n, bool)]


def _clear_pending():
    """Set pending_post_merge to [] in the state file (atomic temp+rename).
    Best-effort: a missing/malformed state file or write error is reported on
    stderr but does not fail the run (phases already completed)."""
    path = _state_path()
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, ValueError) as e:
        sys.stderr.write(
            f"run-post-merge: cannot read state to clear pending: {e}\n"
        )
        return
    state["pending_post_merge"] = []
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except OSError as e:
        sys.stderr.write(f"run-post-merge: cannot clear pending: {e}\n")
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _run_phase(script_name, args):
    """Invoke a sibling phase script. Returns its CompletedProcess. Phase
    stderr is passed through so the caller's log carries diagnostics; phase
    stdout is captured into the result JSON (NOT echoed to our stdout, which
    must stay a single parseable result object)."""
    script = os.path.join(_script_dir(), script_name)
    proc = subprocess.run(
        [sys.executable, script, *args],
        capture_output=True, text=True,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc


def run():
    pending = _read_pending()
    if not pending:
        json.dump({"status": "noop", "pending": []}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    pr_list = ",".join(str(n) for n in pending)
    result = {"status": "completed", "pending": pending, "phases": {}}

    # Phase 7 — release (once per PR). release-bump.py exits 0 even when it
    # SKIPS or FAILS the release (status in its stdout JSON), so success is
    # keyed on that status, not the exit code (issue #512). A skipped/failed/
    # unparseable release leaves pending_post_merge intact for the next
    # tick's drain to retry.
    release = []
    for pr in pending:
        proc = _run_phase("release-bump.py", [str(pr)])
        try:
            release_status = json.loads(proc.stdout or "").get("status")
        except (ValueError, AttributeError):
            release_status = None
        entry = {"pr": pr, "returncode": proc.returncode,
                 "release_status": release_status}
        release.append(entry)
        if proc.returncode != 0 or release_status != "released":
            entry["release_json"] = (proc.stdout or "").strip()
            result["status"] = "failed"
            result["phases"]["release"] = release
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 1
    result["phases"]["release"] = release

    # Phase 8 — cleanup (once with the whole list).
    proc = _run_phase("cleanup-branches.py", [pr_list])
    result["phases"]["cleanup"] = {"pr_list": pr_list,
                                   "returncode": proc.returncode}
    if proc.returncode != 0:
        result["status"] = "failed"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    # Phase 9 — catch-up (once per PR).
    catchup = []
    for pr in pending:
        proc = _run_phase("classify-merge-restart.py", [str(pr)])
        catchup.append({"pr": pr, "returncode": proc.returncode,
                        "rung": (proc.stdout or "").strip()})
        if proc.returncode != 0:
            result["status"] = "failed"
            result["phases"]["catch_up"] = catchup
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 1
    result["phases"]["catch_up"] = catchup

    # All phases succeeded — clear the owed-work list.
    _clear_pending()

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main():
    argparse.ArgumentParser(
        description="Deterministically run tick phases 7-9 (release -> "
                    "cleanup -> catch-up) for every PR in the state's "
                    "pending_post_merge list, then clear it. Clean no-op when "
                    "the list is empty. Exits non-zero on any phase failure."
    ).parse_args()
    return run()


if __name__ == "__main__":
    sys.exit(main())
