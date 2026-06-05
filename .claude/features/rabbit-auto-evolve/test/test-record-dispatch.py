#!/usr/bin/env python3
"""test-record-dispatch.py — e2e tests for scripts/record-dispatch.py (Inv 54).

Covers the script-owned dispatch-journal WRITE point:

  - --help smoke
  - an append records a journal entry under tick-id with status `dispatched`
  - a repeated call for the same (tick-id, issue) UPDATES in place, never
    duplicates (and can promote the status / fill branch/pr)
  - `started_at` is seeded once per tick and not overwritten by a later entry
  - a second issue under the same tick appends a second entry
  - a missing state file errors (non-zero exit, nothing written)
  - the written journal validates through update-state.py (schema 1.4.0)

Tests use tempfile.TemporaryDirectory() and the RABBIT_AUTO_EVOLVE_STATE_DIR
env var; a seeded valid state file is the journal substrate.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "record-dispatch.py"))
UPDATE_STATE = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "update-state.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _seed_state(state_dir, extra=None):
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
    if extra:
        state.update(extra)
    path = os.path.join(state_dir, "auto-evolve-state.json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
    return path


def _run(args, state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, env=env,
    )


def _read_state(state_dir):
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        return json.load(f)


# A — --help smoke
proc = subprocess.run([sys.executable, SCRIPT, "--help"],
                      capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"A: --help should exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
elif "usage" not in (proc.stdout + proc.stderr).lower():
    fail("A: --help output should contain 'usage'")
else:
    ok("A: --help exits 0 with usage text")


# B — an append records a `dispatched` entry under the tick-id
with tempfile.TemporaryDirectory() as td:
    _seed_state(td)
    proc = _run(["--tick-id", "tick-1", "--issue", "815",
                 "--feature", "rabbit-housekeep",
                 "--shape", "parallel-per-feature",
                 "--status", "dispatched"], td)
    if proc.returncode != 0:
        fail(f"B: record should exit 0; stderr={proc.stderr!r}")
    else:
        st = _read_state(td)
        journal = st.get("dispatch_journal", {})
        tick = journal.get("tick-1", {})
        entries = tick.get("entries", [])
        if len(entries) != 1:
            fail(f"B: expected 1 entry, got {entries!r}")
        else:
            e = entries[0]
            if (e.get("issue") != 815 or e.get("feature") != "rabbit-housekeep"
                    or e.get("shape") != "parallel-per-feature"
                    or e.get("status") != "dispatched"):
                fail(f"B: entry fields wrong: {e!r}")
            elif not tick.get("started_at"):
                fail("B: tick should carry started_at")
            else:
                ok("B: append records a dispatched entry with started_at")


# C — a repeated call for the same (tick, issue) UPDATES in place, no dup
with tempfile.TemporaryDirectory() as td:
    _seed_state(td)
    _run(["--tick-id", "tick-1", "--issue", "815",
          "--feature", "rabbit-housekeep", "--shape", "parallel-per-feature",
          "--status", "dispatched"], td)
    proc = _run(["--tick-id", "tick-1", "--issue", "815",
                 "--feature", "rabbit-housekeep",
                 "--shape", "parallel-per-feature",
                 "--status", "pr_open", "--branch", "feat/815-x",
                 "--pr", "820"], td)
    if proc.returncode != 0:
        fail(f"C: update should exit 0; stderr={proc.stderr!r}")
    else:
        st = _read_state(td)
        entries = st["dispatch_journal"]["tick-1"]["entries"]
        if len(entries) != 1:
            fail(f"C: repeated call must UPDATE in place, not duplicate; "
                 f"got {entries!r}")
        else:
            e = entries[0]
            if (e.get("status") != "pr_open" or e.get("branch") != "feat/815-x"
                    or e.get("pr") != 820):
                fail(f"C: update did not record new fields: {e!r}")
            else:
                ok("C: repeated call updates the entry in place (no dup)")


# D — started_at seeded once and preserved across a later entry
with tempfile.TemporaryDirectory() as td:
    _seed_state(td)
    _run(["--tick-id", "tick-1", "--issue", "815", "--feature", "f1",
          "--shape", "parallel-per-feature", "--status", "dispatched"], td)
    started_first = _read_state(td)["dispatch_journal"]["tick-1"]["started_at"]
    _run(["--tick-id", "tick-1", "--issue", "816", "--feature", "f2",
          "--shape", "parallel-per-feature", "--status", "dispatched"], td)
    st = _read_state(td)
    tick = st["dispatch_journal"]["tick-1"]
    if tick["started_at"] != started_first:
        fail("D: started_at must be seeded once and not overwritten")
    elif len(tick["entries"]) != 2:
        fail(f"D: a distinct issue should append a 2nd entry; got {tick['entries']!r}")
    else:
        ok("D: started_at preserved; distinct issue appends a 2nd entry")


# E — a missing state file errors (non-zero, nothing written)
with tempfile.TemporaryDirectory() as td:
    proc = _run(["--tick-id", "tick-1", "--issue", "1", "--feature", "f",
                 "--shape", "parallel-per-feature", "--status", "dispatched"],
                td)
    if proc.returncode == 0:
        fail("E: a missing state file should error (non-zero)")
    elif os.path.exists(os.path.join(td, "auto-evolve-state.json")):
        fail("E: no state file should be created on the error path")
    else:
        ok("E: a missing state file errors, nothing written")


# F — the written journal validates through update-state.py (schema 1.4.0)
with tempfile.TemporaryDirectory() as td:
    _seed_state(td)
    _run(["--tick-id", "tick-1", "--issue", "815", "--feature", "f1",
          "--shape", "parallel-per-feature", "--status", "dispatched"], td)
    st = _read_state(td)
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = td
    proc = subprocess.run([sys.executable, UPDATE_STATE], input=json.dumps(st),
                          capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        fail(f"F: recorded journal should validate through update-state.py; "
             f"stderr={proc.stderr!r}")
    else:
        ok("F: recorded journal validates through update-state.py (1.4.0)")


sys.exit(FAIL)
