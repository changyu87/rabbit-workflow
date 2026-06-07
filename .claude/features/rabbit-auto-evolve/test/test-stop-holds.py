#!/usr/bin/env python3
"""test-stop-holds.py — e2e tests for Inv 41: a user stop HOLDS across cron
heartbeats; only an explicit user `start` clears the stop marker.

The control-safety defect this guards: a cron-fired wake-up that fires the
USER-intent `/rabbit-auto-evolve start` inherits `start-loop.py`'s stop-cancel
semantics (Inv 19), silently resurrecting a loop the user explicitly stopped.
The fix routes every MACHINE (cron / immediate-refire) wake-up through
`/rabbit-auto-evolve tick`, the internal phase-walk, which RESPECTS the stop
marker at phase 0 and NEVER deletes it. The marker is cleared EXCLUSIVELY by
an explicit user `start` (`start-loop.py`, Inv 19).

Scenarios (acceptance criteria from the bug):
  A) stop marker present + a cron-fired tick (tick-headless.py) -> halts at
     phase 0, marker NOT deleted, no phase work done.
  B) stop marker present + explicit user start (start-loop.py) -> marker
     cleared, loop resumes (Inv 19 preserved for the user path).
  C) across N simulated heartbeats with a pending stop -> zero ticks perform
     work; the marker persists every time.
  D) the headless tick's phase-0 stop short-circuit READS the marker only —
     it never deletes it (guards run-tick-phases.py pre-dispatch).
  E) schedule-decision.py emits /rabbit-auto-evolve tick (NOT start) for the
     immediate-refire prompt AND the croncreate one-shot prompt.
  F) install-cron.py's restricted-host croncreate heartbeat prompt is
     /rabbit-auto-evolve tick (NOT start).
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
TICK_HEADLESS = os.path.join(SCRIPTS, "tick-headless.py")
START_LOOP = os.path.join(SCRIPTS, "start-loop.py")
DECIDE = os.path.join(SCRIPTS, "schedule-decision.py")
INSTALL = os.path.join(SCRIPTS, "install-cron.py")

STOP_MARKER = ".rabbit-auto-evolve-stop-requested"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# Stub phase scripts for the headless tick — each appends its name to a trace
# file so we can assert NO phase work runs while a stop is pending.
STUBS = {
    "sync-tree.py": "print('{\"status\": \"synced\"}')",
    "fetch-queue.py": "print('[]')",
    "triage-batch.py": "import sys; sys.stdin.read(); print('[]')",
    "plan-batch.py": "import sys; sys.stdin.read(); print('{}')",
    "merge-prs.py": "print('[]')",
    "run-post-merge.py": "print('{\"status\": \"noop\", \"pending\": []}')",
    "update-state.py": "import sys; sys.stdin.read(); print('{\"ok\": true}')",
    "running-guard.py": "print('{\"action\": \"proceed\"}')",
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


def read_trace(trace_file):
    if not os.path.isfile(trace_file):
        return []
    with open(trace_file) as f:
        return [ln.strip() for ln in f if ln.strip()]


def run_headless(repo_root, script_dir, state_dir, trace_file):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, TICK_HEADLESS], cwd=repo_root,
        capture_output=True, text=True, env=env,
    )


def write_state(state_dir):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump({"queue": [], "in_flight": [], "merge_ready": []}, f)


# ---------------------------------------------------------------------------
# A — stop marker present + a cron-fired tick -> halts, marker NOT deleted,
#     no phase work runs.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    write_state(state_dir)
    stop_path = os.path.join(repo_root, STOP_MARKER)
    open(stop_path, "w").close()

    proc = run_headless(repo_root, script_dir, state_dir, trace)
    if proc.returncode == 0:
        ok("A: cron-fired tick exited 0 (clean halt) with stop pending")
    else:
        fail(f"A: tick exit {proc.returncode}; stderr={proc.stderr!r}")
    if os.path.exists(stop_path):
        ok("A: stop marker NOT deleted by a cron-fired tick")
    else:
        fail("A: cron-fired tick DELETED the stop marker (loop resurrected)")
    phases = [x for x in read_trace(trace) if x != "sync-tree.py"]
    if not phases:
        ok("A: no phase work ran while a stop was pending")
    else:
        fail(f"A: phase work ran despite the pending stop: {phases!r}")


# ---------------------------------------------------------------------------
# B — explicit user start clears the stop marker (Inv 19 preserved).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    stop_path = os.path.join(repo_root, STOP_MARKER)
    open(stop_path, "w").close()
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    proc = subprocess.run(
        [sys.executable, START_LOOP], capture_output=True, text=True, env=env,
    )
    if proc.returncode == 0:
        ok("B: explicit user start exited 0")
    else:
        fail(f"B: start-loop exit {proc.returncode}; stderr={proc.stderr!r}")
    if not os.path.exists(stop_path):
        ok("B: explicit user start CLEARED the stop marker (Inv 19)")
    else:
        fail("B: user start did not clear the stop marker (Inv 19 broken)")
    # Per Inv 35 the running-marker write moved into the shared phase-walk;
    # start-loop.py (the explicit-start entry) no longer writes it. The Inv 19
    # contract this scenario guards is the stop-cancel above, not the marker.
    if not os.path.exists(os.path.join(repo_root, ".rabbit-auto-evolve-running")):
        ok("B: start-loop did not write the running marker (Inv 35: walk owns it)")
    else:
        fail("B: start-loop wrote the running marker (Inv 35: walk owns it)")


# ---------------------------------------------------------------------------
# C — across N heartbeats with a pending stop, zero ticks do work and the
#     marker persists each time.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    write_state(state_dir)
    stop_path = os.path.join(repo_root, STOP_MARKER)
    open(stop_path, "w").close()

    N = 5
    all_clean = True
    for i in range(N):
        proc = run_headless(repo_root, script_dir, state_dir, trace)
        if proc.returncode != 0:
            all_clean = False
            fail(f"C: heartbeat {i} exit {proc.returncode}; stderr={proc.stderr!r}")
        if not os.path.exists(stop_path):
            all_clean = False
            fail(f"C: stop marker vanished after heartbeat {i}")
    phases = [x for x in read_trace(trace) if x != "sync-tree.py"]
    if all_clean and not phases:
        ok(f"C: {N} heartbeats with a pending stop did zero work; marker persisted")
    elif phases:
        fail(f"C: phase work ran across heartbeats: {phases!r}")


# ---------------------------------------------------------------------------
# D — the pre-dispatch phase-0 short-circuit READS the marker only.
#     (Re-running a single headless tick must leave the marker in place — a
#     direct guard against any future regression that deletes-on-read.)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    write_state(state_dir)
    stop_path = os.path.join(repo_root, STOP_MARKER)
    open(stop_path, "w").close()
    run_headless(repo_root, script_dir, state_dir, trace)
    if os.path.exists(stop_path):
        ok("D: phase-0 stop-check reads the marker without deleting it")
    else:
        fail("D: phase-0 stop-check deleted the marker (must only READ)")


# ---------------------------------------------------------------------------
# E — schedule-decision.py emits /rabbit-auto-evolve tick (NOT start).
# ---------------------------------------------------------------------------
def make_fetch_shim(dirpath, json_array):
    shim = os.path.join(dirpath, "fetch-queue-shim.py")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys
            sys.stdout.write({json_array!r})
            sys.exit(0)
            """))
    os.chmod(shim, 0o755)
    return shim


def make_crontab_shim(dirpath, restricted):
    shim = os.path.join(dirpath, "crontab")
    if restricted:
        body = ('import sys\n'
                'sys.stderr.write("You (t) are not allowed to use this '
                'program (crontab)\\n")\nsys.exit(1)\n')
    else:
        body = 'import sys\nsys.exit(0)\n'
    with open(shim, "w") as f:
        f.write(f"#!{sys.executable}\n" + body)
    os.chmod(shim, 0o755)
    return shim


def make_plan_shim(dirpath, selection_order):
    """A plan-batch.py stand-in emitting a canned `selection_order` so this
    test drives schedule-decision's dispatchable-work gate (#1004) without
    shelling `gh` through the real triage|plan pipe."""
    shim = os.path.join(dirpath, "plan-batch-shim.py")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import json, sys
            sys.stdin.read()
            sys.stdout.write(json.dumps({{"selection_order": {selection_order!r}}}))
            sys.exit(0)
            """))
    os.chmod(shim, 0o755)
    return shim


def make_triage_shim(dirpath):
    """A no-op triage-batch.py stand-in (the plan shim ignores its output)."""
    shim = os.path.join(dirpath, "triage-batch-shim.py")
    with open(shim, "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys
            sys.stdin.read()
            sys.stdout.write("[]")
            sys.exit(0)
            """))
    os.chmod(shim, 0o755)
    return shim


def run_decide(d, queue_json, restricted=False, selection_order=(1,)):
    """Run schedule-decision with a non-empty DISPATCHABLE plan by default
    (Inv 33 / #1004 now keys the refire off the fetch|triage|plan pipe's
    selection_order, not the raw open count), so the refire-prompt assertions
    below still exercise the immediate-refire path."""
    fetch = make_fetch_shim(d, queue_json)
    cron = make_crontab_shim(d, restricted)
    triage = make_triage_shim(d)
    plan = make_plan_shim(d, list(selection_order))
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD"] = fetch
    env["RABBIT_AUTO_EVOLVE_TRIAGE_BATCH_CMD"] = triage
    env["RABBIT_AUTO_EVOLVE_PLAN_BATCH_CMD"] = plan
    env["RABBIT_CRONTAB_CMD"] = cron
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(d, ".rabbit")
    return subprocess.run(
        [sys.executable, DECIDE], capture_output=True, text=True, env=env,
    )


NONEMPTY = '[{"number": 1, "title": "x", "labels": []}]'

with tempfile.TemporaryDirectory() as d:
    proc = run_decide(d, NONEMPTY, restricted=False)
    try:
        j = json.loads(proc.stdout)
    except json.JSONDecodeError:
        j = None
    # Inv 41: the refire fires the internal `tick`, NEVER `start`. Inv 33
    # (#559): the refire prompt ALSO carries the #refire marker.
    prompt = (j or {}).get("prompt", "")
    if prompt.startswith("/rabbit-auto-evolve tick") and "start" not in prompt:
        ok("E: immediate-refire prompt is /rabbit-auto-evolve tick (not start)")
    else:
        fail(f"E: refire prompt is not 'tick': {j!r}")

with tempfile.TemporaryDirectory() as d:
    proc = run_decide(d, NONEMPTY, restricted=True)
    try:
        j = json.loads(proc.stdout)
    except json.JSONDecodeError:
        j = None
    cc = (j or {}).get("croncreate")
    cc_prompt = (cc or {}).get("prompt", "") if isinstance(cc, dict) else ""
    if cc_prompt.startswith("/rabbit-auto-evolve tick") and "start" not in cc_prompt:
        ok("E: croncreate one-shot prompt is /rabbit-auto-evolve tick (not start)")
    else:
        fail(f"E: croncreate prompt is not 'tick': {cc!r}")


# ---------------------------------------------------------------------------
# F — install-cron.py's restricted-host heartbeat prompt is the internal tick.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    os.makedirs(repo_root)
    shim = make_crontab_shim(d, restricted=True)
    env = os.environ.copy()
    env["RABBIT_CRONTAB_CMD"] = shim
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    proc = subprocess.run(
        [sys.executable, INSTALL], capture_output=True, text=True, env=env,
    )
    signal = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and "croncreate" in line:
            try:
                signal = json.loads(line)
            except json.JSONDecodeError:
                signal = None
            break
    if signal and signal.get("prompt") == "/rabbit-auto-evolve tick":
        ok("F: croncreate heartbeat prompt is /rabbit-auto-evolve tick (not start)")
    else:
        fail(f"F: heartbeat prompt is not 'tick': {signal!r}")


sys.exit(FAIL)
