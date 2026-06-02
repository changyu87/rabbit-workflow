#!/usr/bin/env python3
"""test-state-persistence.py — e2e tests for scripts/update-state.py (Inv 9).

Covers the spec'd surface of `scripts/update-state.py` and
`scripts/schemas/auto-evolve-state.schema.json`:

  - --help smoke
  - round-trip: pipe a valid state object in → assert written file equals input
  - missing-required-field: each required field omitted → non-zero exit,
    stderr names the field, file NOT created
  - restart_needed typing: accept null and string; reject bool and int with
    type-mismatch detail in stderr
  - atomicity: pre-create a stale state file; update with new content; read
    back; assert new content (no partial / no merge)

Tests use tempfile.TemporaryDirectory() and the RABBIT_AUTO_EVOLVE_STATE_DIR
env var to redirect the write target to the tempdir.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "update-state.py"))
SCHEMA = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "schemas",
                 "auto-evolve-state.schema.json"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _valid_state():
    """A fully-populated valid state object matching the Inv 9 schema."""
    return {
        "schema_version": "1.0.0",
        "updated_at": "2026-06-02T12:34:56Z",
        "queue": [
            {"issue": 101, "decision": "work", "feature": "rabbit-issue"},
            {"issue": 102, "decision": "defer", "feature": "rabbit-cage"},
        ],
        "in_flight": [201, 202],
        "last_merged_sha": "abc1234567890abcdef1234567890abcdef1234",
        "last_tagged_version": "v0.5.3",
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
    }


def _run(stdin_text, state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc


# ---------------------------------------------------------------------------
# Scenario A — --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    fail(f"A: --help should exit 0, got {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("A: --help exited 0")
help_text = (proc.stdout + proc.stderr).lower()
if "usage" not in help_text:
    fail(f"A: --help output should contain 'usage'; got stdout={proc.stdout!r}")
else:
    ok("A: --help output contains 'usage'")


# ---------------------------------------------------------------------------
# Scenario B — schema file exists and is well-formed JSON
# ---------------------------------------------------------------------------
if not os.path.isfile(SCHEMA):
    fail(f"B: schema file not found at {SCHEMA}")
else:
    try:
        with open(SCHEMA) as f:
            schema_obj = json.load(f)
        for key in ("schema_version", "owner", "deprecation_criterion"):
            if key not in schema_obj:
                fail(f"B: schema missing top-level metadata key {key!r}")
                break
        else:
            ok("B: schema file present, parseable, and carries metadata")
    except json.JSONDecodeError as e:
        fail(f"B: schema is not valid JSON: {e}")


# ---------------------------------------------------------------------------
# Scenario C — round-trip valid state through update-state.py
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"C: valid state should exit 0; got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        final_path = os.path.join(td, "auto-evolve-state.json")
        if not os.path.exists(final_path):
            fail(f"C: expected file not written at {final_path}")
        else:
            with open(final_path) as f:
                written = json.load(f)
            if written != state:
                fail(f"C: round-trip mismatch; wrote={state} read={written}")
            else:
                ok("C: valid state round-trips through update-state.py")


# ---------------------------------------------------------------------------
# Scenario D — missing-required-field for each required field
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = [
    "schema_version", "updated_at", "queue", "in_flight",
    "last_merged_sha", "last_tagged_version",
    "consecutive_failures", "stop_requested", "restart_needed",
]

for field in REQUIRED_FIELDS:
    with tempfile.TemporaryDirectory() as td:
        state = _valid_state()
        state.pop(field)
        proc = _run(json.dumps(state), td)
        final_path = os.path.join(td, "auto-evolve-state.json")
        if proc.returncode == 0:
            fail(f"D[{field}]: expected non-zero exit when {field} missing; got 0")
        elif os.path.exists(final_path):
            fail(f"D[{field}]: state file was written despite validation failure")
        elif field not in proc.stderr:
            fail(f"D[{field}]: stderr should name the missing field; got {proc.stderr!r}")
        else:
            ok(f"D[{field}]: missing field rejected and file NOT created")


# ---------------------------------------------------------------------------
# Scenario E — restart_needed typing rule (resolved Q3)
# Accept: null, "some reason"
# Reject: True (bool), 42 (int)
# ---------------------------------------------------------------------------
# E1 — accept null
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["restart_needed"] = None
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"E1: restart_needed=null should be accepted; stderr={proc.stderr!r}")
    else:
        ok("E1: restart_needed=null accepted")

# E2 — accept string
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["restart_needed"] = "settings.json change"
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"E2: restart_needed=string should be accepted; stderr={proc.stderr!r}")
    else:
        final_path = os.path.join(td, "auto-evolve-state.json")
        with open(final_path) as f:
            got = json.load(f)
        if got["restart_needed"] != "settings.json change":
            fail(f"E2: restart_needed string not preserved; got {got['restart_needed']!r}")
        else:
            ok("E2: restart_needed=string accepted and preserved")

# E3 — reject bool (True)
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["restart_needed"] = True
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode == 0:
        fail("E3: restart_needed=True (bool) should be rejected; got exit 0")
    elif os.path.exists(final_path):
        fail("E3: state file written despite type-mismatch on restart_needed")
    elif "restart_needed" not in proc.stderr:
        fail(f"E3: stderr should name restart_needed; got {proc.stderr!r}")
    else:
        ok("E3: restart_needed=True (bool) rejected")

# E4 — reject int
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["restart_needed"] = 42
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode == 0:
        fail("E4: restart_needed=42 (int) should be rejected; got exit 0")
    elif os.path.exists(final_path):
        fail("E4: state file written despite type-mismatch on restart_needed")
    elif "restart_needed" not in proc.stderr:
        fail(f"E4: stderr should name restart_needed; got {proc.stderr!r}")
    else:
        ok("E4: restart_needed=42 (int) rejected")


# ---------------------------------------------------------------------------
# Scenario F — atomicity: stale file overwritten cleanly (no merge / partial)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    stale = {
        "schema_version": "1.0.0",
        "updated_at": "2020-01-01T00:00:00Z",
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 99,
        "stop_requested": True,
        "restart_needed": "stale reason",
    }
    final_path = os.path.join(td, "auto-evolve-state.json")
    with open(final_path, "w") as f:
        json.dump(stale, f)

    new_state = _valid_state()
    proc = _run(json.dumps(new_state), td)
    if proc.returncode != 0:
        fail(f"F: update should succeed over stale file; stderr={proc.stderr!r}")
    else:
        with open(final_path) as f:
            got = json.load(f)
        if got != new_state:
            fail(f"F: stale not cleanly overwritten; got {got}")
        elif got.get("consecutive_failures") == 99:
            fail("F: stale field consecutive_failures bled through (partial merge)")
        else:
            ok("F: stale file cleanly overwritten (atomic, no merge)")


# ---------------------------------------------------------------------------
# Scenario G — malformed JSON on stdin → non-zero exit, no file write
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    proc = _run("not valid json at all", td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode == 0:
        fail("G: malformed JSON should be rejected; got exit 0")
    elif os.path.exists(final_path):
        fail("G: state file written despite malformed stdin")
    else:
        ok("G: malformed stdin JSON rejected")


sys.exit(FAIL)
