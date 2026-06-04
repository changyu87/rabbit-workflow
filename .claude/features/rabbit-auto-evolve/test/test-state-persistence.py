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
        "schema_version": "1.3.0",
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
        "schema_version": "1.3.0",
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


# ---------------------------------------------------------------------------
# Scenario H — issue #423 Part B: schema_version is bumped to 1.1.0 and the
# new optional `defer_counts` field (map of issue-number string → int) is
# accepted and round-trips. Old states WITHOUT defer_counts still validate
# (additive change).
# ---------------------------------------------------------------------------
# H1 — schema_version const is 1.3.0 (issue #721 bumped 1.2.0 -> 1.3.0)
with open(SCHEMA) as f:
    schema_obj = json.load(f)
if schema_obj.get("schema_version") != "1.3.0":
    fail(f"H1: schema top-level schema_version "
         f"{schema_obj.get('schema_version')!r} != '1.3.0'")
else:
    ok("H1: schema_version bumped to 1.3.0")

# H2 — defer_counts accepted and round-trips
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["defer_counts"] = {"500": 2, "600": 1}
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"H2: defer_counts should be accepted; stderr={proc.stderr!r}")
    else:
        with open(os.path.join(td, "auto-evolve-state.json")) as f:
            got = json.load(f)
        if got.get("defer_counts") != {"500": 2, "600": 1}:
            fail(f"H2: defer_counts not preserved; got {got.get('defer_counts')!r}")
        else:
            ok("H2: defer_counts accepted and round-trips")

# H3 — a state WITHOUT defer_counts still validates (additive / optional)
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()  # no defer_counts key
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"H3: state without defer_counts should still validate; "
             f"stderr={proc.stderr!r}")
    else:
        ok("H3: defer_counts is optional (state without it validates)")


# ---------------------------------------------------------------------------
# Scenario I — issue #499: schema 1.2.0 adds the optional `pending_post_merge`
# field (array of int — merged PR numbers owed phases 7-9). Accepted and
# round-trips; states WITHOUT it still validate (additive); a non-int element
# is rejected.
# ---------------------------------------------------------------------------
# I1 — pending_post_merge accepted and round-trips
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["pending_post_merge"] = [10, 20, 30]
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"I1: pending_post_merge should be accepted; "
             f"stderr={proc.stderr!r}")
    else:
        with open(os.path.join(td, "auto-evolve-state.json")) as f:
            got = json.load(f)
        if got.get("pending_post_merge") != [10, 20, 30]:
            fail(f"I1: pending_post_merge not preserved; "
                 f"got {got.get('pending_post_merge')!r}")
        else:
            ok("I1: pending_post_merge accepted and round-trips")

# I2 — a state WITHOUT pending_post_merge still validates (additive)
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()  # no pending_post_merge key
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"I2: state without pending_post_merge should still validate; "
             f"stderr={proc.stderr!r}")
    else:
        ok("I2: pending_post_merge is optional (state without it validates)")

# I3 — a non-int element is rejected with a type-mismatch naming the field
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["pending_post_merge"] = [10, "x"]
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode == 0:
        fail("I3: pending_post_merge with a non-int element should be rejected")
    elif os.path.exists(final_path):
        fail("I3: state file written despite invalid pending_post_merge")
    elif "pending_post_merge" not in proc.stderr:
        fail(f"I3: stderr should name pending_post_merge; got {proc.stderr!r}")
    else:
        ok("I3: pending_post_merge with a non-int element rejected")


# ---------------------------------------------------------------------------
# Scenario J — issue #721: schema 1.3.0 adds the optional
# `decomposition_parents` map (parent-issue-number string -> list of child
# issue numbers). Accepted and round-trips; states WITHOUT it still validate
# (additive); a non-int child element is rejected with a field-naming message.
# ---------------------------------------------------------------------------
# J1 — decomposition_parents accepted and round-trips
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["decomposition_parents"] = {"677": [679, 680, 681]}
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"J1: decomposition_parents should be accepted; "
             f"stderr={proc.stderr!r}")
    else:
        with open(os.path.join(td, "auto-evolve-state.json")) as f:
            got = json.load(f)
        if got.get("decomposition_parents") != {"677": [679, 680, 681]}:
            fail(f"J1: decomposition_parents not preserved; "
                 f"got {got.get('decomposition_parents')!r}")
        else:
            ok("J1: decomposition_parents accepted and round-trips")

# J2 — a state WITHOUT decomposition_parents still validates (additive)
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()  # no decomposition_parents key
    proc = _run(json.dumps(state), td)
    if proc.returncode != 0:
        fail(f"J2: state without decomposition_parents should still validate; "
             f"stderr={proc.stderr!r}")
    else:
        ok("J2: decomposition_parents is optional (state without it validates)")

# J3 — a non-int child element is rejected, stderr naming the field
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["decomposition_parents"] = {"677": [679, "x"]}
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode == 0:
        fail("J3: decomposition_parents with a non-int child should be "
             "rejected")
    elif os.path.exists(final_path):
        fail("J3: state file written despite invalid decomposition_parents")
    elif "decomposition_parents" not in proc.stderr:
        fail(f"J3: stderr should name decomposition_parents; "
             f"got {proc.stderr!r}")
    else:
        ok("J3: decomposition_parents with a non-int child rejected")


# ---------------------------------------------------------------------------
# Scenario K — issue #761: migrate-in-place for an OLDER on-disk schema version
# whose delta to current is purely ADDITIVE. update-state.py should accept the
# older version, fill any new optional fields with documented defaults, set
# schema_version to current, then validate — rather than hard-failing. A
# newer/unknown version still errors. A current-version file is untouched.
# ---------------------------------------------------------------------------
def _state_at(version):
    """A valid 1.3.0 state body re-stamped at an older schema_version, with the
    optional fields introduced AFTER that version removed (simulating a real
    older on-disk state)."""
    s = _valid_state()
    s["schema_version"] = version
    s.pop("defer_counts", None)
    s.pop("pending_post_merge", None)
    s.pop("decomposition_parents", None)
    return s

# K1 — a 1.2.0 state (no decomposition_parents) is migrated to 1.3.0, the new
# field is defaulted to {}, the write succeeds (exit 0), and the persisted file
# carries schema_version 1.3.0 with decomposition_parents == {}.
with tempfile.TemporaryDirectory() as td:
    state = _state_at("1.2.0")
    if "decomposition_parents" in state:
        fail("K1: test setup error — 1.2.0 fixture should omit "
             "decomposition_parents")
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode != 0:
        fail(f"K1: 1.2.0 state should migrate and persist (exit 0); "
             f"got {proc.returncode}; stderr={proc.stderr!r}")
    elif not os.path.exists(final_path):
        fail("K1: migrated state file not written")
    else:
        with open(final_path) as f:
            got = json.load(f)
        if got.get("schema_version") != "1.3.0":
            fail(f"K1: schema_version not migrated to 1.3.0; "
                 f"got {got.get('schema_version')!r}")
        elif got.get("decomposition_parents") != {}:
            fail(f"K1: decomposition_parents not defaulted to {{}}; "
                 f"got {got.get('decomposition_parents')!r}")
        else:
            ok("K1: 1.2.0 state migrated to 1.3.0 (decomposition_parents={})")

# K2 — a current 1.3.0 state is untouched (idempotent migration / no-op): it
# persists exactly as supplied, byte-for-byte semantically equal.
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()  # already 1.3.0, no optional fields
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode != 0:
        fail(f"K2: current 1.3.0 state should persist (exit 0); "
             f"stderr={proc.stderr!r}")
    else:
        with open(final_path) as f:
            got = json.load(f)
        # idempotent: a current-version state with no optional fields is NOT
        # mutated by migration (no spurious optional-field injection).
        if got != state:
            fail(f"K2: current 1.3.0 state was mutated by migration; "
                 f"wrote={state} read={got}")
        else:
            ok("K2: current 1.3.0 state untouched (migration is a no-op)")

# K3 — a newer-than-known version (9.9.9) still ERRORS clearly, names
# schema_version, and does NOT write the file.
with tempfile.TemporaryDirectory() as td:
    state = _valid_state()
    state["schema_version"] = "9.9.9"
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode == 0:
        fail("K3: newer/unknown version 9.9.9 should be rejected; got exit 0")
    elif os.path.exists(final_path):
        fail("K3: state file written despite unknown newer version")
    elif "schema_version" not in proc.stderr:
        fail(f"K3: stderr should name schema_version; got {proc.stderr!r}")
    else:
        ok("K3: newer/unknown version 9.9.9 rejected, file NOT written")

# K4 — a 1.1.0 state migrates UP THE LADDER through 1.2.0 to 1.3.0, defaulting
# BOTH pending_post_merge (->[]) and decomposition_parents (->{}).
with tempfile.TemporaryDirectory() as td:
    state = _state_at("1.1.0")
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode != 0:
        fail(f"K4: 1.1.0 state should migrate through ladder (exit 0); "
             f"got {proc.returncode}; stderr={proc.stderr!r}")
    else:
        with open(final_path) as f:
            got = json.load(f)
        if got.get("schema_version") != "1.3.0":
            fail(f"K4: schema_version not migrated to 1.3.0; "
                 f"got {got.get('schema_version')!r}")
        elif got.get("pending_post_merge") != []:
            fail(f"K4: pending_post_merge not defaulted to []; "
                 f"got {got.get('pending_post_merge')!r}")
        elif got.get("decomposition_parents") != {}:
            fail(f"K4: decomposition_parents not defaulted to {{}}; "
                 f"got {got.get('decomposition_parents')!r}")
        else:
            ok("K4: 1.1.0 state migrated up the ladder to 1.3.0")

# K5 — an unknown OLDER version not on the ladder (e.g. 1.0.0) still ERRORS
# clearly rather than silently passing through.
with tempfile.TemporaryDirectory() as td:
    state = _state_at("1.0.0")
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode == 0:
        fail("K5: unknown older version 1.0.0 (not on ladder) should be "
             "rejected; got exit 0")
    elif os.path.exists(final_path):
        fail("K5: state file written despite unknown older version")
    elif "schema_version" not in proc.stderr:
        fail(f"K5: stderr should name schema_version; got {proc.stderr!r}")
    else:
        ok("K5: unknown older version 1.0.0 rejected, file NOT written")

# K6 — migration preserves existing data already present in an older state
# (an older 1.2.0 state that DOES carry defer_counts keeps it intact).
with tempfile.TemporaryDirectory() as td:
    state = _state_at("1.2.0")
    state["defer_counts"] = {"500": 3}
    proc = _run(json.dumps(state), td)
    final_path = os.path.join(td, "auto-evolve-state.json")
    if proc.returncode != 0:
        fail(f"K6: 1.2.0 state with defer_counts should migrate (exit 0); "
             f"stderr={proc.stderr!r}")
    else:
        with open(final_path) as f:
            got = json.load(f)
        if got.get("defer_counts") != {"500": 3}:
            fail(f"K6: existing defer_counts lost during migration; "
                 f"got {got.get('defer_counts')!r}")
        elif got.get("schema_version") != "1.3.0":
            fail(f"K6: schema_version not migrated; "
                 f"got {got.get('schema_version')!r}")
        else:
            ok("K6: migration preserves pre-existing optional data")


sys.exit(FAIL)
