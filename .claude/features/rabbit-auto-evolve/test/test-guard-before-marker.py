#!/usr/bin/env python3
"""test-guard-before-marker.py — e2e tests for Inv 42: run-tick-phases.py runs
its running-guard FIRST and writes the .rabbit-auto-evolve-running marker ONLY
after the guard returns `proceed`, so neither the in-session nor the headless
path ever false-skips on a marker it itself wrote.

The defect this guards (the in-session false-skip): before this fix the
in-session `start` sequence wrote the running marker BEFORE invoking the walk;
the walk's pre-dispatch then re-ran the running-guard, saw the loop's OWN fresh
live marker, and returned `{action: skip, reason: tick-running}` — false-skipping
the entire tick on the marker the loop itself just wrote.

The fix: the shared phase-walk (`run-tick-phases.py pre-dispatch`) runs the
running-guard FIRST and, only on `proceed`, writes the running marker itself
(the durable owner-PID + ISO-timestamp write `start-loop.py` used to do). The
guard never trips on a marker the walk wrote within the SAME call.

Concurrency protection is preserved: a marker from a DIFFERENT live tick that
already exists BEFORE the walk starts still makes the guard skip.

Scenarios (acceptance criteria from the bug):
  A) clean state (no marker, no stop/abort) -> walk runs the guard, writes the
     running marker, returns action: proceed; the marker exists afterward and
     the result is NOT a self-skip.
  B) the walk does NOT false-skip on a marker it itself wrote within the same
     call (the #565 regression guard) — exercised against the REAL guard.
  C) a FRESH marker from a DIFFERENT live tick present BEFORE the walk starts
     still makes pre-dispatch SKIP (concurrency protection preserved).
  D) start-loop.py (the explicit user `start` entry) cancels a pending stop
     (Inv 19) and does NOT itself write the running marker (the walk owns it).
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
WALK = os.path.join(SCRIPTS, "run-tick-phases.py")
START_LOOP = os.path.join(SCRIPTS, "start-loop.py")

RUNNING_MARKER = ".rabbit-auto-evolve-running"
STOP_MARKER = ".rabbit-auto-evolve-stop-requested"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# Stub phase scripts (the deterministic phases 2-4 + sync). The running-guard
# and update-state are deliberately the REAL scripts in the scenarios that
# exercise the guard->mark ordering, so the marker write/guard interaction is
# end-to-end.
STUBS = {
    "sync-tree.py": "print('{\"status\": \"synced\"}')",
    "fetch-queue.py": "print('[]')",
    "triage-batch.py": "import sys; sys.stdin.read(); print('[]')",
    "plan-batch.py": "import sys; sys.stdin.read(); print('{}')",
}


def make_stub_scripts(dirpath, trace_file):
    for name, body in STUBS.items():
        path = os.path.join(dirpath, name)
        with open(path, "w") as f:
            f.write(textwrap.dedent(f"""\
                #!{sys.executable}
                import sys
                with open({trace_file!r}, "a") as _t:
                    _t.write({name!r} + "\\n")
                {body}
                """))
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def install_real(script_dir, names):
    for name in names:
        shutil.copy(os.path.join(SCRIPTS, name), os.path.join(script_dir, name))
    # running-guard.py imports tick-log.py by file spec; provide a stub so the
    # best-effort logging append does not error in the hermetic dir.
    tick_log = os.path.join(script_dir, "tick-log.py")
    if not os.path.exists(tick_log):
        with open(tick_log, "w") as f:
            f.write("def append(decision, detail):\n    pass\n")


def run_pre_dispatch(repo_root, script_dir, state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, WALK, "pre-dispatch"],
        cwd=repo_root, capture_output=True, text=True, env=env,
    )


def fresh(d):
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    os.makedirs(state_dir)
    make_stub_scripts(script_dir, trace)
    install_real(script_dir, ["running-guard.py"])
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump({"queue": [], "in_flight": []}, f)
    return repo_root, state_dir, script_dir


# ---------------------------------------------------------------------------
# A — clean state: walk runs the guard, writes the running marker, proceeds.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir = fresh(d)
    marker = os.path.join(repo_root, RUNNING_MARKER)
    if os.path.exists(marker):
        fail("A: running marker existed before the walk (test setup bug)")
    proc = run_pre_dispatch(repo_root, script_dir, state_dir)
    if proc.returncode != 0:
        fail(f"A: pre-dispatch exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("A: pre-dispatch exited 0 on clean state")
    try:
        res = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        res = {}
        fail(f"A: pre-dispatch stdout not JSON: {proc.stdout!r}")
    if res.get("action") != "proceed":
        fail(f"A: clean-state result not 'proceed' (self-skip?): {res!r}")
    else:
        ok("A: clean-state result signals proceed (no self-skip)")
    if os.path.exists(marker):
        ok("A: walk wrote the running marker after the guard returned proceed")
    else:
        fail("A: walk did NOT write the running marker on proceed")
    content = open(marker).read() if os.path.exists(marker) else ""
    if "ts=" in content and content.rstrip().endswith("session"):
        ok("A: running marker carries the durable owner-PID/timestamp content")
    else:
        fail(f"A: running marker content shape unexpected: {content!r}")


# ---------------------------------------------------------------------------
# B — #565 regression guard: the walk must NOT false-skip on the marker it
#     itself wrote within the same call. Exercised with the REAL guard.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir = fresh(d)
    proc = run_pre_dispatch(repo_root, script_dir, state_dir)
    try:
        res = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        res = {}
    if res.get("action") == "skip" and res.get("reason") == "tick-running":
        fail("B: walk false-skipped 'tick-running' on its OWN marker (#565)")
    elif res.get("action") == "proceed":
        ok("B: walk did NOT self-skip on the marker it wrote (#565 fixed)")
    else:
        fail(f"B: unexpected pre-dispatch result: {res!r}")


# ---------------------------------------------------------------------------
# C — concurrency protection: a FRESH marker from a DIFFERENT live tick present
#     BEFORE the walk starts still makes pre-dispatch SKIP. We simulate "fresh"
#     via a live owner PID (this test process) recorded in the marker, which the
#     real running-guard treats as an active tick.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir = fresh(d)
    marker = os.path.join(repo_root, RUNNING_MARKER)
    with open(marker, "w") as f:
        f.write(f"pid={os.getpid()} ts=2026-06-03T00:00:00Z session")
    proc = run_pre_dispatch(repo_root, script_dir, state_dir)
    try:
        res = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        res = {}
    if res.get("action") == "skip" and res.get("reason") == "tick-running":
        ok("C: pre-dispatch SKIPS on a different live tick's pre-existing marker")
    else:
        fail(f"C: concurrency protection lost — expected skip, got {res!r}")
    trace = os.path.join(d, "trace.txt")
    phases = []
    if os.path.isfile(trace):
        phases = [ln.strip() for ln in open(trace)
                  if ln.strip() and ln.strip() != "sync-tree.py"]
    if phases:
        fail(f"C: phases ran despite the live-tick skip: {phases!r}")
    else:
        ok("C: no phase work ran on the concurrency skip")


# ---------------------------------------------------------------------------
# D — start-loop.py (explicit user start) cancels a pending stop (Inv 19) and
#     does NOT itself write the running marker (the walk owns the marker write).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    stop_path = os.path.join(repo_root, STOP_MARKER)
    open(stop_path, "w").close()
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    proc = subprocess.run([sys.executable, START_LOOP],
                          capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        fail(f"D: start-loop exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("D: start-loop exited 0")
    if not os.path.exists(stop_path):
        ok("D: explicit start cancelled the pending stop (Inv 19)")
    else:
        fail("D: explicit start did NOT cancel the pending stop (Inv 19 broken)")
    if os.path.exists(os.path.join(repo_root, RUNNING_MARKER)):
        fail("D: start-loop wrote the running marker (must be owned by the walk)")
    else:
        ok("D: start-loop did NOT write the running marker (walk owns it)")
    # Bootstrap still tied to explicit start.
    if os.path.isfile(os.path.join(repo_root, ".rabbit", "auto-evolve-state.json")):
        ok("D: explicit start bootstrapped the state file (Inv 19)")
    else:
        fail("D: explicit start did NOT bootstrap the state file (Inv 19 broken)")


sys.exit(FAIL)
