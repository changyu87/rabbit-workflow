#!/usr/bin/env python3
"""test-close-decomposed-parents.py — e2e tests for
scripts/close-decomposed-parents.py (Inv 53 / issue #721).

close-decomposed-parents.py reads the state's `decomposition_parents` map and,
for every tracked parent whose recorded children are ALL closed, closes the
parent (`gh issue close <parent> --reason completed`) and drops the parent key.
A parent with any open child is left untouched. Covered surface:

  - --help smoke
  - ALL children closed -> parent CLOSED (gh issue close invoked for the
    parent with --reason completed) AND the parent key removed from
    decomposition_parents in the written state
  - ONE child still OPEN -> parent NOT closed (no gh issue close for it) AND
    the parent key RETAINED
  - mixed map (one closeable parent, one with an open child) -> only the
    closeable parent is closed/removed; the other is retained
  - empty / absent decomposition_parents -> clean no-op (no gh issue close,
    exit 0)

Fixtures: a PATH-resident `gh` shim that (a) answers
`gh issue view <n> --json state` from a per-child state table baked into the
shim, and (b) logs every `gh issue close ...` invocation to a call log.
State_dir is supplied via RABBIT_AUTO_EVOLVE_STATE_DIR.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(
    os.path.join(HERE, "..", "scripts", "close-decomposed-parents.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def _seed_state(state_dir, decomposition_parents):
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
        "decomposition_parents": decomposition_parents,
    }
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f)


def _read_state(state_dir):
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        return json.load(f)


def _write_gh_shim(bin_dir, states, close_log):
    """Write a `gh` shim that answers `issue view <n> --json state` from the
    `states` map (number -> "OPEN"/"CLOSED") and logs `issue close <n> ...`
    invocations (one argv line each) to close_log."""
    shim = os.path.join(bin_dir, "gh")
    py = [
        "#!/usr/bin/env python3",
        "import json, sys",
        f"STATES = {json.dumps({str(k): v for k, v in states.items()})}",
        f"CLOSE_LOG = {close_log!r}",
        "a = sys.argv[1:]",
        "if len(a) >= 2 and a[0] == 'issue' and a[1] == 'view':",
        "    num = a[2]",
        "    st = STATES.get(str(num), 'OPEN')",
        "    sys.stdout.write(json.dumps({'number': int(num), 'state': st}))",
        "    sys.exit(0)",
        "if len(a) >= 2 and a[0] == 'issue' and a[1] == 'close':",
        "    with open(CLOSE_LOG, 'a') as f:",
        "        f.write(' '.join(a) + '\\n')",
        "    sys.exit(0)",
        "sys.stderr.write('unexpected gh invocation: ' + ' '.join(a) + '\\n')",
        "sys.exit(3)",
        "",
    ]
    with open(shim, "w") as f:
        f.write("\n".join(py))
    os.chmod(shim, stat.S_IRWXU)


def _make_env(td, states):
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir)
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    close_log = os.path.join(td, "close.log")
    open(close_log, "w").close()
    _write_gh_shim(bin_dir, states, close_log)
    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return state_dir, close_log, env


def _closes(close_log):
    with open(close_log) as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]


def _closed_parents(close_log):
    """Return the set of parent numbers passed to `gh issue close`."""
    out = set()
    for ln in _closes(close_log):
        parts = ln.split()
        # issue close <n> ...
        if len(parts) >= 3 and parts[0] == "issue" and parts[1] == "close":
            out.add(parts[2])
    return out


def _run(env):
    return subprocess.run(
        [sys.executable, SCRIPT], env=env, capture_output=True, text=True)


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


# --- ALL children closed -> parent closed + key dropped -------------------
with tempfile.TemporaryDirectory() as td:
    states = {679: "CLOSED", 680: "CLOSED", 681: "CLOSED"}
    state_dir, close_log, env = _make_env(td, states)
    _seed_state(state_dir, {"677": [679, 680, 681]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"all-closed: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("all-closed: exit 0")
    if "677" not in _closed_parents(close_log):
        fail(f"all-closed: parent 677 not closed; closes={_closes(close_log)!r}")
    else:
        ok("all-closed: parent 677 closed via gh issue close")
    # --reason completed must be present on the close call.
    if not any("--reason completed" in ln for ln in _closes(close_log)):
        fail(f"all-closed: close not --reason completed; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("all-closed: close used --reason completed")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if "677" in dp:
        fail(f"all-closed: parent key 677 not removed; dp={dp!r}")
    else:
        ok("all-closed: parent key removed from decomposition_parents")


# --- ONE child open -> parent untouched, key retained ---------------------
with tempfile.TemporaryDirectory() as td:
    states = {679: "CLOSED", 680: "OPEN", 681: "CLOSED"}
    state_dir, close_log, env = _make_env(td, states)
    _seed_state(state_dir, {"677": [679, 680, 681]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"one-open: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("one-open: exit 0")
    if "677" in _closed_parents(close_log):
        fail(f"one-open: parent 677 closed despite an open child; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("one-open: parent 677 NOT closed (open child present)")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if dp.get("677") != [679, 680, 681]:
        fail(f"one-open: parent key 677 not retained intact; dp={dp!r}")
    else:
        ok("one-open: parent key retained")


# --- mixed: one closeable, one not ----------------------------------------
with tempfile.TemporaryDirectory() as td:
    states = {679: "CLOSED", 680: "CLOSED",  # parent 677 closeable
              531: "CLOSED", 532: "OPEN"}    # parent 530 NOT closeable
    state_dir, close_log, env = _make_env(td, states)
    _seed_state(state_dir, {"677": [679, 680], "530": [531, 532]})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"mixed: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("mixed: exit 0")
    closed = _closed_parents(close_log)
    if "677" not in closed:
        fail(f"mixed: closeable parent 677 not closed; closes={closed!r}")
    else:
        ok("mixed: closeable parent 677 closed")
    if "530" in closed:
        fail(f"mixed: parent 530 closed despite open child; closes={closed!r}")
    else:
        ok("mixed: parent 530 NOT closed")
    dp = _read_state(state_dir).get("decomposition_parents", {})
    if "677" in dp or dp.get("530") != [531, 532]:
        fail(f"mixed: state not updated correctly; dp={dp!r}")
    else:
        ok("mixed: 677 removed, 530 retained")


# --- empty map -> clean no-op ---------------------------------------------
with tempfile.TemporaryDirectory() as td:
    state_dir, close_log, env = _make_env(td, {})
    _seed_state(state_dir, {})
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"empty: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("empty: exit 0")
    if _closes(close_log):
        fail(f"empty: gh issue close invoked on empty map; "
             f"closes={_closes(close_log)!r}")
    else:
        ok("empty: no gh issue close invoked (clean no-op)")


# --- absent decomposition_parents -> clean no-op --------------------------
with tempfile.TemporaryDirectory() as td:
    bin_dir = os.path.join(td, "bin")
    os.makedirs(bin_dir)
    state_dir = os.path.join(td, "state")
    os.makedirs(state_dir)
    close_log = os.path.join(td, "close.log")
    open(close_log, "w").close()
    _write_gh_shim(bin_dir, {}, close_log)
    env = os.environ.copy()
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    # state WITHOUT a decomposition_parents key
    state = {
        "schema_version": "1.3.0",
        "updated_at": "2026-06-04T00:00:00Z",
        "queue": [], "in_flight": [],
        "last_merged_sha": None, "last_tagged_version": None,
        "consecutive_failures": 0, "stop_requested": False,
        "restart_needed": None,
    }
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(state, f)
    proc = _run(env)
    if proc.returncode != 0:
        fail(f"absent: exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("absent: exit 0 (no decomposition_parents key is a clean no-op)")
    if _closes(close_log):
        fail(f"absent: gh issue close invoked; closes={_closes(close_log)!r}")
    else:
        ok("absent: no gh issue close invoked")


sys.exit(FAIL)
