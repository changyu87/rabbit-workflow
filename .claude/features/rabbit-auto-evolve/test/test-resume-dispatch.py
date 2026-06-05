#!/usr/bin/env python3
"""test-resume-dispatch.py — e2e tests for scripts/resume-dispatch.py (Inv 54).

Covers the script-owned dispatch-journal READ/RESUME point. It reads a plan
JSON on stdin (carrying `selection_order`) and the active tick's journal, and
emits `{"dispatch": [...], "skip": [...]}`:

  - --help smoke
  - `completed` -> SKIP; `pr_open` -> SKIP
  - `dispatched` with no PR -> RE-dispatch; `aborted` -> RE-dispatch
  - an issue absent from the journal -> dispatch normally
  - an empty / absent journal -> every planned issue dispatched (no-regression)
  - partition is exhaustive: dispatch ∪ skip == selection_order, disjoint
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "resume-dispatch.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _seed_state(state_dir, journal=None):
    state = {
        "schema_version": "1.4.0",
        "updated_at": "2026-06-04T12:00:00Z",
        "queue": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
    }
    if journal is not None:
        state["dispatch_journal"] = journal
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f, indent=2)


def _run(plan, args, state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        input=json.dumps(plan), capture_output=True, text=True, env=env,
    )


def _entry(issue, status, pr=None):
    return {"issue": issue, "feature": "f", "shape": "parallel-per-feature",
            "branch": None, "worktree": None, "pr": pr, "status": status}


# A — --help smoke
proc = subprocess.run([sys.executable, SCRIPT, "--help"],
                      capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"A: --help should exit 0, got {proc.returncode}")
elif "usage" not in (proc.stdout + proc.stderr).lower():
    fail("A: --help output should contain 'usage'")
else:
    ok("A: --help exits 0 with usage text")


# B — completed/pr_open SKIP; dispatched-no-PR/aborted/absent RE-dispatch
with tempfile.TemporaryDirectory() as td:
    journal = {"tick-1": {"started_at": "2026-06-04T12:00:00Z", "entries": [
        _entry(801, "completed", pr=901),
        _entry(802, "pr_open", pr=902),
        _entry(803, "dispatched"),
        _entry(804, "aborted"),
    ]}}
    _seed_state(td, journal)
    plan = {"selection_order": [801, 802, 803, 804, 805]}
    proc = _run(plan, ["--tick-id", "tick-1"], td)
    if proc.returncode != 0:
        fail(f"B: should exit 0; stderr={proc.stderr!r}")
    else:
        out = json.loads(proc.stdout)
        dispatch = sorted(out.get("dispatch", []))
        skip = sorted(out.get("skip", []))
        if dispatch != [803, 804, 805]:
            fail(f"B: dispatch set wrong; got {dispatch!r} "
                 f"(want [803, 804, 805])")
        elif skip != [801, 802]:
            fail(f"B: skip set wrong; got {skip!r} (want [801, 802])")
        else:
            ok("B: completed/pr_open SKIP; dispatched-no-PR/aborted/absent "
               "re-dispatch")


# C — empty journal: every planned issue dispatched (no-regression)
with tempfile.TemporaryDirectory() as td:
    _seed_state(td, {})
    plan = {"selection_order": [10, 20, 30]}
    proc = _run(plan, ["--tick-id", "tick-1"], td)
    out = json.loads(proc.stdout)
    if sorted(out.get("dispatch", [])) != [10, 20, 30] or out.get("skip"):
        fail(f"C: empty journal should dispatch all; got {out!r}")
    else:
        ok("C: empty journal dispatches every planned issue (no-regression)")


# D — absent journal field entirely: dispatch all
with tempfile.TemporaryDirectory() as td:
    _seed_state(td, None)
    plan = {"selection_order": [5, 6]}
    proc = _run(plan, ["--tick-id", "tick-1"], td)
    out = json.loads(proc.stdout)
    if sorted(out.get("dispatch", [])) != [5, 6] or out.get("skip"):
        fail(f"D: absent journal should dispatch all; got {out!r}")
    else:
        ok("D: absent journal dispatches every planned issue")


# E — partition exhaustive + disjoint
with tempfile.TemporaryDirectory() as td:
    journal = {"tick-7": {"started_at": "2026-06-04T12:00:00Z", "entries": [
        _entry(1, "completed", pr=11),
        _entry(2, "dispatched"),
    ]}}
    _seed_state(td, journal)
    plan = {"selection_order": [1, 2, 3, 4]}
    proc = _run(plan, ["--tick-id", "tick-7"], td)
    out = json.loads(proc.stdout)
    dispatch = set(out.get("dispatch", []))
    skip = set(out.get("skip", []))
    if dispatch | skip != {1, 2, 3, 4}:
        fail(f"E: dispatch ∪ skip must equal selection_order; got "
             f"dispatch={dispatch} skip={skip}")
    elif dispatch & skip:
        fail(f"E: dispatch and skip must be disjoint; overlap={dispatch & skip}")
    else:
        ok("E: partition is exhaustive and disjoint")


sys.exit(FAIL)
