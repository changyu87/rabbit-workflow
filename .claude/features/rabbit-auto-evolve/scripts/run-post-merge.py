#!/usr/bin/env python3
"""run-post-merge.py — deterministic, non-skippable runner for tick phases 8-10.

Usage:
  run-post-merge.py

Per rabbit-auto-evolve spec.md Inv 30 (issue #499), tick phases 8 (release),
8 (cleanup), and 9 (catch-up) were prose in SKILL.md walked by the LLM
orchestrator. After phase 7 (merge) landed a large batch of PRs, the
orchestrator ended the tick for scale/context reasons and phases 8-10 were
silently dropped — the same class of failure as the LLM-walked-prose skips
in #405 / #409 / #439. This script owns the phase-7-through-9 sequencing so
the steps are deterministic and non-skippable.

It:
  1. Reads `pending_post_merge` (array of merged PR numbers owed post-merge
     processing) from `<state_dir>/auto-evolve-state.json`.
  2. If empty / missing / malformed → CLEAN NO-OP: emit
     {"status": "noop", "pending": []} and exit 0 (no phase script invoked).
  3. Otherwise, in order:
       - Phase 8 (release):  `release-bump.py <pr#>` once per PR.
       - Phase 9 (cleanup):  `cleanup-branches.py <comma-joined pr-list>` once.
       - Phase 10 (catch-up): `classify-merge-restart.py <pr#>` once per PR.
  4. Runs the decomposed-parent roll-up (`close-decomposed-parents.py`,
     Inv 53 / #721) AFTER catch-up on the non-empty path AND on the empty
     no-op path (a decomposition's children close on their OWN ticks, not
     only when a PR merges). It closes every tracked decomposition parent
     whose children are all closed and drops the parent key; a clean no-op
     when nothing is tracked.
  5. On completion (all phase scripts exited 0 AND every release-bump.py
     reported status "released"), clears `pending_post_merge` to [] in the
     state file (atomic via temp+rename).
  6. Emits a result JSON object on stdout recording the pending set and each
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

Issue #838 (Inv 54): the same step that clears pending_post_merge also prunes
fully-drained (all-completed/aborted) ticks from the dispatch_journal, bounding
its on-disk growth.

Version: 1.3.0
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


def _prune_journal(state):
    """Drop every dispatch_journal tick whose entries are ALL completed/aborted
    (issue #838, Inv 54), bounding the journal's on-disk growth — the
    designed-deprecation end-of-life. A tick with ANY still-`dispatched`/
    `pr_open` entry is KEPT. A tick with no entries is also dropped (nothing to
    resume). Mutates `state` in place; no-op when there is no journal."""
    journal = state.get("dispatch_journal")
    if not isinstance(journal, dict):
        return
    terminal = {"completed", "aborted"}
    survivors = {}
    for tick_id, tick in journal.items():
        if not isinstance(tick, dict):
            continue
        entries = tick.get("entries")
        if not isinstance(entries, list) or not entries:
            continue  # empty tick: nothing to resume, drop it
        if all(isinstance(e, dict) and e.get("status") in terminal
               for e in entries):
            continue  # fully drained: drop it
        survivors[tick_id] = tick
    state["dispatch_journal"] = survivors


def _clear_pending():
    """Set pending_post_merge to [] in the state file (atomic temp+rename) and
    prune fully-drained dispatch_journal ticks (issue #838, Inv 54) in the same
    write. Best-effort: a missing/malformed state file or write error is
    reported on stderr but does not fail the run (phases already completed)."""
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
    _prune_journal(state)
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


def _run_rollup():
    """Run the decomposed-parent roll-up (close-decomposed-parents.py, Inv 53 /
    #721). Returns its CompletedProcess. This runs EVERY tick — even on the
    empty pending_post_merge no-op path — because a decomposition's children
    close on their OWN ticks, not only when a PR merges. A non-zero roll-up
    return is surfaced by the caller but the roll-up is itself a clean no-op
    when nothing is tracked."""
    return _run_phase("close-decomposed-parents.py", [])


def run():
    pending = _read_pending()
    if not pending:
        # The decomposed-parent roll-up runs every tick, including the empty
        # no-op path (Inv 53 / #721): children close on their own ticks.
        rollup = _run_rollup()
        result = {"status": "noop", "pending": [],
                  "phases": {"close_decomposed_parents": rollup.returncode}}
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    pr_list = ",".join(str(n) for n in pending)
    result = {"status": "completed", "pending": pending, "phases": {}}

    # Phase 8 — release (once per PR). release-bump.py exits 0 even when it
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

    # Phase 9 — cleanup (once with the whole list).
    proc = _run_phase("cleanup-branches.py", [pr_list])
    result["phases"]["cleanup"] = {"pr_list": pr_list,
                                   "returncode": proc.returncode}
    if proc.returncode != 0:
        result["status"] = "failed"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    # Phase 10 — catch-up (once per PR).
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

    # Decomposed-parent roll-up (Inv 53 / #721) — runs AFTER catch-up. Closes
    # every tracked decomposition parent whose recorded children are all closed
    # and drops its decomposition_parents key. A non-zero return is recorded
    # but never withholds clearing pending_post_merge (the owed post-merge work
    # already completed) — the next tick's drain retries the roll-up.
    rollup = _run_rollup()
    result["phases"]["close_decomposed_parents"] = rollup.returncode

    # All phases succeeded — clear the owed-work list.
    _clear_pending()

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main():
    argparse.ArgumentParser(
        description="Deterministically run tick phases 8-10 (release -> "
                    "cleanup -> catch-up) for every PR in the state's "
                    "pending_post_merge list, then clear it. Clean no-op when "
                    "the list is empty. Exits non-zero on any phase failure."
    ).parse_args()
    return run()


if __name__ == "__main__":
    sys.exit(main())
