#!/usr/bin/env python3
"""run-tick-phases.py — the single shared scripted phase-walk both the headless
tick (`tick-headless.py`) and the in-session tick (SKILL.md `start`/`tick`)
invoke (Inv 40 / issue #513).

The deterministic tick phases are walked in TWO segments so that Phase 5
(`dispatch`) — the ONLY phase that needs a live Claude session — can be
inserted BETWEEN them by the in-session path without either path
hand-assembling any inter-phase data structure:

  pre-dispatch   tick-start self-sync (Inv 38), phase 0/1 stop/abort
                 short-circuit, running-guard (Inv 35), running-marker WRITE
                 (Inv 42 — only after the guard returns proceed), phases 2-4
                 (fetch | triage | plan, Inv 18). Emits a result with
                 `action: "proceed"` (continue to dispatch) or
                 `action: "skip"` (a clean no-op short-circuit fired).

The running marker is written by THIS shared walk (after its own guard),
not before it by the caller (Inv 42). Sequencing the guard BEFORE the marker
write — in ONE place for both the in-session and headless paths — means neither
path false-skips on a marker it itself wrote. start-loop.py (the explicit user
`start` entry) keeps ONLY its cancel-stop + bootstrap self-heal (Inv 19) and no
longer writes the running marker.

  post-dispatch  phase 6 (merge ready PRs from the state's `merge_ready`
                 hint), a post-merge re-sync to origin/dev when PRs merged
                 (Inv 47), phases 7-9 (`run-post-merge.py` drain), phase 10
                 (persist: re-read the on-disk state — already mutated by the
                 phase scripts — drop the transient `merge_ready` key, and
                 pipe through `update-state.py`). Emits a result summary.

The headless tick chains:   pre-dispatch -> (skip dispatch) -> post-dispatch.
The in-session tick chains: pre-dispatch -> Phase 5 (Claude) -> post-dispatch.

Every phase handoff is script-to-script (stdin/stdout pipes or on-disk state
mutation). The dispatcher NEVER reads `update-state.py` source or the state
schema to hand-assemble the new-state object — Phase 10 re-reads from disk and
pipes the existing object back through `update-state.py`, identically in both
paths.

Resolution (matching the sibling scripts):
  - sibling scripts via `RABBIT_AUTO_EVOLVE_SCRIPT_DIR`, else this script's dir.
  - repo root (for marker existence checks) via `RABBIT_AUTO_EVOLVE_REPO_ROOT`,
    else `os.getcwd()`.
  - state dir via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else `<cwd>/.rabbit`.

A single JSON result object is emitted on stdout. Exit code is 0 on a
completed segment (including every short-circuit no-op); non-zero on an
unexpected phase-script failure.

Version: 1.3.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys

STOP_MARKER = ".rabbit-auto-evolve-stop-requested"
ABORT_MARKER = ".rabbit-auto-evolve-aborted"
RUNNING_MARKER = ".rabbit-auto-evolve-running"


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
    """The list of PR numbers ready to merge from the state's `merge_ready`
    field. Empty list when missing/malformed."""
    ready = _read_state().get("merge_ready")
    if not isinstance(ready, list):
        return []
    return [n for n in ready if isinstance(n, int) and not isinstance(n, bool)]


def _run(script_name, args, stdin_text=None):
    """Invoke a sibling phase script. Returns its CompletedProcess. Phase
    stderr is passed through; stdout is returned for piping/capture."""
    script = os.path.join(_script_dir(), script_name)
    proc = subprocess.run(
        [sys.executable, script, *args],
        input=stdin_text,
        capture_output=True, text=True,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc


def _emit(result):
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _write_running_marker():
    """Write the .rabbit-auto-evolve-running marker at the repo root, carrying
    the DURABLE owner PID + ISO-8601 timestamp the running-guard reads (Inv 35).

    The marker write is owned by the shared phase-walk and runs ONLY after the
    running-guard returns `proceed` (Inv 42), so neither the in-session nor the
    headless path ever false-skips on a marker it itself wrote. The durable
    owner-PID + timestamp content shape lives in start-loop.py (imported by file
    spec, since the filename is hyphenated) so the marker content stays defined
    in ONE place. start-loop.py is always a sibling of this script, so it is
    resolved next to THIS file (not via the configurable phase-script dir, which
    a test harness may point at stub phase scripts)."""
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "start_loop", os.path.join(here, "start-loop.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    path = os.path.join(_repo_root(), RUNNING_MARKER)
    with open(path, "w") as f:
        f.write(mod._marker_content())


def run_pre_dispatch():
    """Phases: tick-start sync (Inv 38) -> phase 0/1 stop/abort short-circuit
    -> running-guard (Inv 35) -> running-marker write (Inv 42, only on proceed)
    -> phases 2-4 fetch|triage|plan (Inv 18).

    Returns `(result_dict, exit_code)`. The result's `action` is "proceed"
    (continue to dispatch) or "skip" (a clean no-op short-circuit fired). On a
    phase-script failure, status is "failed" and exit_code is 1. The caller
    owns emitting the result (so the headless tick can fold this into its
    combined result object)."""
    repo_root = _repo_root()
    result = {"segment": "pre-dispatch", "action": "proceed",
              "status": "completed", "phases": {}}

    # tick-start working-tree self-sync (Inv 38 / #524).
    sync = _run("sync-tree.py", [])
    result["phases"]["sync"] = sync.returncode
    if sync.returncode != 0:
        result["action"] = "skip"
        result["status"] = "noop"
        result["reason"] = "sync-failed"
        return result, 0

    # phase 0 / 1: stop / abort short-circuit.
    if os.path.exists(os.path.join(repo_root, STOP_MARKER)):
        result["action"] = "skip"
        result["status"] = "noop"
        result["reason"] = "stop-requested"
        return result, 0
    if os.path.exists(os.path.join(repo_root, ABORT_MARKER)):
        result["action"] = "skip"
        result["status"] = "noop"
        result["reason"] = "aborted"
        return result, 0

    # running-guard: staleness-aware "is a tick running?" (Inv 35 / #526).
    guard = _run("running-guard.py", [])
    try:
        verdict = json.loads(guard.stdout)
    except (ValueError, AttributeError):
        verdict = {}
    if verdict.get("action") == "skip":
        result["action"] = "skip"
        result["status"] = "noop"
        result["reason"] = "tick-running"
        return result, 0
    if verdict.get("stale_cleared"):
        result["running_guard"] = "stale-cleared"

    # The guard returned `proceed` (no live marker, or a stale one it cleared).
    # ONLY now does the walk write the running marker (Inv 42), so the guard
    # above never trips on a marker the walk itself wrote. Both the in-session
    # and headless paths get the marker written this single way.
    _write_running_marker()
    result["running_marker"] = "written"

    # phases 2-4: fetch | triage | plan (Inv 18).
    fetch = _run("fetch-queue.py", [])
    result["phases"]["fetch"] = fetch.returncode
    if fetch.returncode != 0:
        result["action"] = "skip"
        result["status"] = "failed"
        result["reason"] = "fetch-failed"
        return result, 1
    triage = _run("triage-batch.py", [], stdin_text=fetch.stdout)
    result["phases"]["triage"] = triage.returncode
    if triage.returncode != 0:
        result["action"] = "skip"
        result["status"] = "failed"
        result["reason"] = "triage-failed"
        return result, 1
    plan = _run("plan-batch.py", ["--max-parallel", "4"], stdin_text=triage.stdout)
    result["phases"]["plan"] = plan.returncode
    if plan.returncode != 0:
        result["action"] = "skip"
        result["status"] = "failed"
        result["reason"] = "plan-failed"
        return result, 1

    return result, 0


def run_post_dispatch():
    """Phases: 6 merge ready PRs -> 7-9 run-post-merge drain -> 10 persist
    (re-read on-disk state, drop transient merge_ready, pipe through
    update-state.py).

    Returns `(result_dict, exit_code)`. The caller owns emitting the result."""
    result = {"segment": "post-dispatch", "status": "completed", "phases": {}}

    # phase 6 (FIRST action, BEFORE merge): deterministic pre-merge cleanup of
    # KNOWN worktree-dispatch leak-class noise from the main tree (Inv 43 /
    # #583). Worktree-isolated Phase 5 dispatches sometimes leak a stray
    # `.rabbit-scope-active-*` marker or a bookkeeping-only `feature.json`
    # edit into the dispatcher's main tree, which trips safety-check Inv 5 and
    # makes merge-prs.py skip the whole batch. The cleanup restores ONLY that
    # known leak class and FAILS LOUDLY on any unexpected tracked change, so a
    # genuine uncommitted change is never destroyed — the tick aborts instead.
    clean = _run("clean-dispatch-leaks.py", [])
    result["phases"]["clean_leaks"] = clean.returncode
    if clean.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "clean-leaks-refused"
        return result, 1

    # phase 6: merge ready PRs (from the transient merge_ready hint).
    ready = _merge_ready()
    if ready:
        pr_list = ",".join(str(n) for n in ready)
        merge = _run("merge-prs.py", [pr_list, "--record-pending"])
        result["phases"]["merge"] = merge.returncode
        if merge.returncode != 0:
            result["status"] = "failed"
            result["reason"] = "merge-failed"
            return result, 1

        # Post-merge re-sync to origin/dev (Inv 47 / #516). merge-prs.py did a
        # REMOTE squash-merge via `gh pr merge`, which advances origin/dev but
        # NOT the loop's LOCAL dev checkout. Fast-forward local dev to
        # origin/dev NOW, before the phases 7-9 release drain, so
        # release-bump.py computes its tag against fresh (not stale) state and
        # succeeds on the FIRST in-loop attempt (no reliance on the #512
        # next-tick retry). Reuses sync-tree.py (git pull --ff-only origin dev,
        # NEVER git merge — Inv 38), inheriting its dirty-tree / non-ff
        # refusal: a tree that cannot be fast-forwarded aborts the tick here
        # rather than running release-bump on stale state. Gated on actual
        # merges — with zero merges origin/dev did not advance, so the re-sync
        # is skipped (harmless no-op, no spurious sync error).
        resync = _run("sync-tree.py", [])
        result["phases"]["resync"] = resync.returncode
        if resync.returncode != 0:
            result["status"] = "failed"
            result["reason"] = "post-merge-resync-failed"
            return result, 1
    else:
        result["phases"]["merge"] = "skipped-no-ready-prs"

    # phases 7-9: post-merge drain (release -> cleanup -> catch-up).
    post = _run("run-post-merge.py", [])
    result["phases"]["post_merge"] = post.returncode
    if post.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "post-merge-failed"
        return result, 1

    # phase 10: persist. Re-read the (phase-script-mutated) on-disk state and
    # write it back through update-state.py. `merge_ready` is a transient
    # per-tick hint (not part of the Inv 9 schema), so drop it before handing
    # the object to update-state.py, whose validator rejects unknown keys.
    state = _read_state()
    state.pop("merge_ready", None)
    persist = _run("update-state.py", [], stdin_text=json.dumps(state))
    result["phases"]["persist"] = persist.returncode
    if persist.returncode != 0:
        result["status"] = "failed"
        result["reason"] = "persist-failed"
        return result, 1

    return result, 0


def main():
    parser = argparse.ArgumentParser(
        description="Run one segment of the shared scripted tick phase-walk. "
                    "`pre-dispatch` walks the tick-start sync, phase 0/1 "
                    "short-circuit, running-guard, and phases 2-4; "
                    "`post-dispatch` walks phase 6 (merge), phases 7-9 "
                    "(post-merge), and phase 10 (persist). Phase 5 (dispatch) "
                    "is inserted between the segments by the in-session path "
                    "only (it needs Claude)."
    )
    parser.add_argument("segment", choices=["pre-dispatch", "post-dispatch"],
                        help="which phase-walk segment to run")
    args = parser.parse_args()
    if args.segment == "pre-dispatch":
        result, code = run_pre_dispatch()
    else:
        result, code = run_post_dispatch()
    _emit(result)
    return code


if __name__ == "__main__":
    sys.exit(main())
