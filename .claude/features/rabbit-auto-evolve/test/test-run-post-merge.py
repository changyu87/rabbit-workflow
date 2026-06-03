#!/usr/bin/env python3
"""test-run-post-merge.py — e2e tests for scripts/run-post-merge.py (Inv 30).

Covers the spec'd surface of `scripts/run-post-merge.py`:
  - --help smoke
  - non-empty pending_post_merge: release-bump.py / cleanup-branches.py /
    classify-merge-restart.py shims each invoked, IN ORDER (release before
    cleanup before catch-up), release+catch-up once per PR, cleanup once with
    the comma-joined list; pending_post_merge cleared to [] in the written
    state; exit 0
  - empty pending_post_merge (and missing state file): clean no-op — no
    phase shim invoked; exit 0; status: noop
  - a phase shim exiting non-zero: run-post-merge.py exits non-zero AND does
    NOT clear pending_post_merge (owed work survives for next tick's drain)
  - a release-bump.py shim emitting {"status":"skipped"} with exit 0:
    run-post-merge.py exits non-zero, does NOT invoke cleanup/catch-up, and
    does NOT clear pending_post_merge (issue #512 — a skipped release is an
    owed release, not a success)

Fixtures: a script_dir holding shims for the three phase scripts (resolved by
run-post-merge.py via RABBIT_AUTO_EVOLVE_SCRIPT_DIR), each appending its
argv to a shared ordered call log; and a state_dir (via
RABBIT_AUTO_EVOLVE_STATE_DIR) seeded with auto-evolve-state.json.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "run-post-merge.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _write_phase_shim(script_dir, name, call_log, exit_code=0, stdout=None):
    """Write a phase-script shim that appends 'name <argv...>' to call_log
    (one line per call), optionally prints `stdout` verbatim, then exits
    exit_code."""
    shim = os.path.join(script_dir, name)
    with open(shim, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import sys\n")
        f.write(f"with open({call_log!r}, 'a') as _f:\n")
        f.write(f"    _f.write({name!r} + ' ' + ' '.join(sys.argv[1:]) + '\\n')\n")
        if stdout is not None:
            f.write(f"sys.stdout.write({stdout!r})\n")
        f.write(f"sys.exit({exit_code})\n")
    os.chmod(shim, stat.S_IRWXU)


def _seed_state(state_dir, pending):
    state = {
        "schema_version": "1.2.0",
        "updated_at": "2026-06-03T00:00:00Z",
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
        "pending_post_merge": pending,
    }
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f)


def _make_env(tmpdir, release_exit=0, cleanup_exit=0, catchup_exit=0,
              release_status="released"):
    script_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(script_dir)
    state_dir = os.path.join(tmpdir, "state")
    os.makedirs(state_dir)
    call_log = os.path.join(tmpdir, "phase-calls.log")
    open(call_log, "w").close()

    release_stdout = (json.dumps({"status": release_status}) + "\n"
                      if release_status is not None else None)
    _write_phase_shim(script_dir, "release-bump.py", call_log, release_exit,
                      stdout=release_stdout)
    _write_phase_shim(script_dir, "cleanup-branches.py", call_log, cleanup_exit)
    _write_phase_shim(script_dir, "classify-merge-restart.py", call_log,
                      catchup_exit)

    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return script_dir, state_dir, call_log, env


def _calls(call_log):
    with open(call_log) as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _read_state(state_dir):
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        return json.load(f)


def _run(env, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        env=env, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
if "usage" not in (proc.stdout + proc.stderr).lower():
    fail(f"help: 'usage' missing; stdout={proc.stdout!r}")
else:
    ok("help: usage text present")


# ---------------------------------------------------------------------------
# Non-empty pending_post_merge = [10, 20]: all three phases invoked, in order;
# release + catch-up once per PR; cleanup once with comma-joined list;
# pending_post_merge cleared to []; exit 0.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    script_dir, state_dir, call_log, env = _make_env(td)
    _seed_state(state_dir, [10, 20])
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"nonempty: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("nonempty: exit 0")

    calls = _calls(call_log)
    names = [c.split()[0] for c in calls]

    # Each phase script must appear.
    if "release-bump.py" not in names:
        fail(f"nonempty: release-bump.py not invoked; calls={calls!r}")
    else:
        ok("nonempty: release-bump.py (phase 7) invoked")
    if "cleanup-branches.py" not in names:
        fail(f"nonempty: cleanup-branches.py not invoked; calls={calls!r}")
    else:
        ok("nonempty: cleanup-branches.py (phase 8) invoked")
    if "classify-merge-restart.py" not in names:
        fail(f"nonempty: classify-merge-restart.py not invoked; "
             f"calls={calls!r}")
    else:
        ok("nonempty: classify-merge-restart.py (phase 9) invoked")

    # Ordering: every release call precedes every cleanup call precedes every
    # catch-up call.
    rel_idx = [i for i, n in enumerate(names) if n == "release-bump.py"]
    cln_idx = [i for i, n in enumerate(names) if n == "cleanup-branches.py"]
    cat_idx = [i for i, n in enumerate(names)
               if n == "classify-merge-restart.py"]
    if rel_idx and cln_idx and cat_idx and \
            max(rel_idx) < min(cln_idx) < max(cln_idx + cat_idx) and \
            max(cln_idx) < min(cat_idx):
        ok("nonempty: phases invoked in order release -> cleanup -> catch-up")
    else:
        fail(f"nonempty: phase ordering wrong; names={names!r}")

    # release-bump.py once per PR (10 and 20).
    rel_calls = [c for c in calls if c.startswith("release-bump.py")]
    rel_args = sorted(c.split()[1] for c in rel_calls if len(c.split()) > 1)
    if rel_args != ["10", "20"]:
        fail(f"nonempty: release-bump.py per-PR args {rel_args!r} != "
             f"['10','20']")
    else:
        ok("nonempty: release-bump.py invoked once per PR (10, 20)")

    # catch-up once per PR.
    cat_calls = [c for c in calls if c.startswith("classify-merge-restart.py")]
    cat_args = sorted(c.split()[1] for c in cat_calls if len(c.split()) > 1)
    if cat_args != ["10", "20"]:
        fail(f"nonempty: classify-merge-restart.py per-PR args {cat_args!r} "
             f"!= ['10','20']")
    else:
        ok("nonempty: classify-merge-restart.py invoked once per PR (10, 20)")

    # cleanup once with comma-joined list.
    cln_calls = [c for c in calls if c.startswith("cleanup-branches.py")]
    if len(cln_calls) != 1:
        fail(f"nonempty: cleanup-branches.py invoked {len(cln_calls)} times, "
             f"expected 1; calls={cln_calls!r}")
    else:
        arg = cln_calls[0].split()[1] if len(cln_calls[0].split()) > 1 else ""
        if arg != "10,20":
            fail(f"nonempty: cleanup-branches.py arg {arg!r} != '10,20'")
        else:
            ok("nonempty: cleanup-branches.py invoked once with '10,20'")

    # pending_post_merge cleared.
    state = _read_state(state_dir)
    if state.get("pending_post_merge") != []:
        fail(f"nonempty: pending_post_merge not cleared; "
             f"got {state.get('pending_post_merge')!r}")
    else:
        ok("nonempty: pending_post_merge cleared to []")


# ---------------------------------------------------------------------------
# Empty pending_post_merge: clean no-op, no phase invoked, status noop.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    script_dir, state_dir, call_log, env = _make_env(td)
    _seed_state(state_dir, [])
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"empty: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("empty: exit 0")
    if _calls(call_log):
        fail(f"empty: a phase shim was invoked; calls={_calls(call_log)!r}")
    else:
        ok("empty: no phase shim invoked (clean no-op)")
    try:
        out = json.loads(proc.stdout)
        if out.get("status") != "noop":
            fail(f"empty: status {out.get('status')!r} != 'noop'")
        else:
            ok("empty: status noop")
    except json.JSONDecodeError as e:
        fail(f"empty: stdout not JSON: {e}; stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Missing state file: clean no-op (the legitimate fresh-clone case).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    script_dir, state_dir, call_log, env = _make_env(td)
    # do not seed any state file
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"missing: expected exit 0, got {proc.returncode}; "
             f"stderr={proc.stderr!r}")
    else:
        ok("missing: exit 0 (no state file is a clean no-op)")
    if _calls(call_log):
        fail(f"missing: a phase shim was invoked; calls={_calls(call_log)!r}")
    else:
        ok("missing: no phase shim invoked")


# ---------------------------------------------------------------------------
# A phase shim exiting non-zero (release-bump.py fails): run-post-merge.py
# exits non-zero AND pending_post_merge is NOT cleared.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    script_dir, state_dir, call_log, env = _make_env(td, release_exit=3)
    _seed_state(state_dir, [10, 20])
    proc = _run(env)
    if proc.returncode == 0:
        fail("phase-fail: expected non-zero exit when a phase script fails; "
             "got 0")
    else:
        ok("phase-fail: non-zero exit on phase-script failure")
    state = _read_state(state_dir)
    if state.get("pending_post_merge") != [10, 20]:
        fail(f"phase-fail: pending_post_merge should survive a phase failure; "
             f"got {state.get('pending_post_merge')!r}")
    else:
        ok("phase-fail: pending_post_merge NOT cleared (owed work survives)")


# ---------------------------------------------------------------------------
# release-bump.py emits {"status":"skipped"} with exit 0 (issue #512): a
# skipped release is an owed release, not a success. run-post-merge.py must
# exit non-zero, NOT invoke cleanup/catch-up, and NOT clear
# pending_post_merge.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    script_dir, state_dir, call_log, env = _make_env(
        td, release_exit=0, release_status="skipped")
    _seed_state(state_dir, [10, 20])
    proc = _run(env)
    if proc.returncode == 0:
        fail("release-skipped: expected non-zero exit when release-bump "
             "status is 'skipped' (exit 0); got 0")
    else:
        ok("release-skipped: non-zero exit on skipped release")

    names = [c.split()[0] for c in _calls(call_log)]
    if "cleanup-branches.py" in names or "classify-merge-restart.py" in names:
        fail(f"release-skipped: cleanup/catch-up invoked after a skipped "
             f"release; calls={names!r}")
    else:
        ok("release-skipped: cleanup/catch-up NOT invoked")

    state = _read_state(state_dir)
    if state.get("pending_post_merge") != [10, 20]:
        fail(f"release-skipped: pending_post_merge should survive a skipped "
             f"release; got {state.get('pending_post_merge')!r}")
    else:
        ok("release-skipped: pending_post_merge NOT cleared (owed work "
           "survives)")

    try:
        out = json.loads(proc.stdout)
        if out.get("status") != "failed":
            fail(f"release-skipped: result status {out.get('status')!r} != "
                 f"'failed'")
        else:
            ok("release-skipped: result status 'failed'")
    except json.JSONDecodeError as e:
        fail(f"release-skipped: stdout not JSON: {e}; stdout={proc.stdout!r}")


sys.exit(FAIL)
