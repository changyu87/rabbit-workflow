#!/usr/bin/env python3
"""test-record-decomposition.py — e2e tests for scripts/record-decomposition.py
(Inv 53 / issue #721).

record-decomposition.py records the machine-readable parent->children linkage
the decomposed-parent roll-up enumerates. Covered surface:
  - --help smoke
  - first record on a fresh state file creates `decomposition_parents` with
    the parent key -> child list, and the round-tripped state validates
    against update-state.py (schema 1.3.0)
  - a second record for a DIFFERENT parent is additive (both keys present)
  - recording children for an EXISTING parent unions the child sets (dedup,
    sorted) rather than clobbering
  - the written state still passes update-state.py validation (schema 1.3.0)

Fixtures: a state_dir (via RABBIT_AUTO_EVOLVE_STATE_DIR) seeded with a
schema-1.3.0 auto-evolve-state.json.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "record-decomposition.py"))
UPDATE_STATE = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "update-state.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _seed_state(state_dir, decomposition_parents=None):
    state = {
        "schema_version": "1.3.0",
        "updated_at": "2026-06-04T00:00:00Z",
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
    }
    if decomposition_parents is not None:
        state["decomposition_parents"] = decomposition_parents
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f)


def _read_state(state_dir):
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        return json.load(f)


def _env(state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return env


def _run(env, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        env=env, capture_output=True, text=True,
    )


def _validates(state_dir):
    """True iff the written state validates through update-state.py."""
    env = _env(state_dir)
    state = _read_state(state_dir)
    proc = subprocess.run(
        [sys.executable, UPDATE_STATE],
        env=env, input=json.dumps(state), capture_output=True, text=True,
    )
    return proc.returncode == 0, proc.stderr


# --- --help smoke ----------------------------------------------------------
proc = subprocess.run([sys.executable, SCRIPT, "--help"],
                      capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail(f"help: 'usage' missing; stdout={proc.stdout!r}")
else:
    ok("help: usage text present")


# --- first record on fresh state ------------------------------------------
with tempfile.TemporaryDirectory() as td:
    _seed_state(td)
    proc = _run(_env(td), "677", "679", "680", "681")
    if proc.returncode != 0:
        fail(f"first: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("first: exit 0")
    state = _read_state(td)
    dp = state.get("decomposition_parents")
    if dp != {"677": [679, 680, 681]}:
        fail(f"first: decomposition_parents {dp!r} != {{'677':[679,680,681]}}")
    else:
        ok("first: parent->children linkage recorded")
    valid, err = _validates(td)
    if not valid:
        fail(f"first: written state fails schema validation: {err!r}")
    else:
        ok("first: written state validates (schema 1.3.0)")


# --- second parent is additive --------------------------------------------
with tempfile.TemporaryDirectory() as td:
    _seed_state(td, {"677": [679, 680]})
    proc = _run(_env(td), "530", "531", "532")
    if proc.returncode != 0:
        fail(f"additive: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("additive: exit 0")
    dp = _read_state(td).get("decomposition_parents")
    if dp != {"677": [679, 680], "530": [531, 532]}:
        fail(f"additive: decomposition_parents {dp!r} not additive")
    else:
        ok("additive: second parent added without clobbering the first")


# --- union for an existing parent (dedup + sorted) ------------------------
with tempfile.TemporaryDirectory() as td:
    _seed_state(td, {"677": [679, 681]})
    proc = _run(_env(td), "677", "680", "679")
    if proc.returncode != 0:
        fail(f"union: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("union: exit 0")
    dp = _read_state(td).get("decomposition_parents")
    if dp != {"677": [679, 680, 681]}:
        fail(f"union: decomposition_parents {dp!r} != "
             f"{{'677':[679,680,681]}} (expected dedup+sorted union)")
    else:
        ok("union: children unioned (dedup + sorted) for existing parent")
    valid, err = _validates(td)
    if not valid:
        fail(f"union: written state fails schema validation: {err!r}")
    else:
        ok("union: written state validates (schema 1.3.0)")


sys.exit(FAIL)
