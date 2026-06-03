#!/usr/bin/env python3
"""test-tick-headless.py — e2e tests for scripts/tick-headless.py (Inv 32 /
issue #414: the headless, Claude-free tick fired by the system cron).

tick-headless.py orchestrates the deterministic tick phases by shelling out
to the sibling phase scripts. To keep these tests hermetic (no gh / git /
network), the tests point RABBIT_AUTO_EVOLVE_SCRIPT_DIR at a tempdir holding
STUB phase scripts that each append their name to a trace file and emit
minimal valid output. The tests then assert which phases ran by reading the
trace file and the emitted result JSON.

Phases exercised (Inv 32):
  - phase 0 stop-check + phase 1 restart-check (marker file existence)
  - phases 2-4 fetch | triage | plan
  - phase 6 merge (of ready PRs from state)
  - phases 7-9 run-post-merge (drain)
  - phase 10 persist (update-state)
  - phase 5 dispatch is NEVER run (requires Claude)
  - phase 11 schedule is a NO-OP (no ScheduleWakeup)

Scenarios:
  A) Normal headless tick: phases 2-4, 6 (with ready PRs), 7-9, 10 run;
     dispatch NEVER appears in the trace; result JSON marks dispatch skipped.
  B) Stop marker present → clean no-op short-circuit (no phase scripts run).
  C) Abort marker present → clean no-op short-circuit.
  D) Empty merge_ready + empty pending → merge & post-merge are clean (no
     merge-prs invocation), tick still completes phases 2-4 + 10.
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
TICK = os.path.join(SCRIPTS, "tick-headless.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# The stub phase scripts. Each appends its identifying token to $TRACE_FILE
# and emits minimal valid stdout for the consumer in the pipe.
STUBS = {
    # sync -> tick-start working-tree self-sync (Inv 38); emits a synced status
    "sync-tree.py": "print('{\"status\": \"synced\"}')",
    # fetch -> emits a JSON array of issues (consumed by triage)
    "fetch-queue.py": "print('[]')",
    # triage -> passthrough emits a JSON array (consumed by plan)
    "triage-batch.py": "import sys; sys.stdin.read(); print('[]')",
    # plan -> passthrough emits a JSON object
    "plan-batch.py": "import sys; sys.stdin.read(); print('{}')",
    # clean-dispatch-leaks -> pre-merge leak cleanup (Inv 43); no-op stub
    "clean-dispatch-leaks.py": "print('{\"status\": \"clean\"}')",
    # merge -> emits a JSON list of per-PR outcomes
    "merge-prs.py": "print('[]')",
    # run-post-merge -> emits the noop/result object
    "run-post-merge.py": "print('{\"status\": \"noop\", \"pending\": []}')",
    # update-state -> reads stdin (state), writes nothing here
    "update-state.py": "import sys; sys.stdin.read(); print('{\"ok\": true}')",
    # dispatch sentinel — if tick-headless ever shells to this it is a bug.
    "dispatch.py": "print('DISPATCH RAN')",
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


def run_tick(repo_root, script_dir, state_dir, trace_file):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    env["RABBIT_TICK_HEADLESS_TRACE"] = trace_file
    return subprocess.run(
        [sys.executable, TICK],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
    )


def read_trace(trace_file):
    if not os.path.isfile(trace_file):
        return []
    with open(trace_file) as f:
        return [ln.strip() for ln in f if ln.strip()]


def write_state(state_dir, mapping):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(mapping, f, indent=2)


# ---------------------------------------------------------------------------
# Scenario A — normal headless tick with ready PRs
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    write_state(state_dir, {
        "schema_version": "1.2.0",
        "queue": [],
        "in_flight": [],
        "merge_ready": [111, 222],
        "pending_post_merge": [],
    })

    proc = run_tick(repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"A: tick exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("A: headless tick exited 0")
    t = read_trace(trace)
    # Inv 38: the working-tree self-sync runs FIRST, before any phase script.
    if "sync-tree.py" not in t:
        fail(f"A: tick-start sync-tree.py did not run; trace={t!r}")
    elif t[0] != "sync-tree.py":
        fail(f"A: sync-tree.py did not run FIRST; trace={t!r}")
    else:
        ok("A: tick-start sync-tree.py ran first (Inv 38)")
    for phase in ("fetch-queue.py", "triage-batch.py", "plan-batch.py"):
        if phase not in t:
            fail(f"A: phase 2-4 script {phase} did not run; trace={t!r}")
        else:
            ok(f"A: phase 2-4 ran {phase}")
    if "merge-prs.py" not in t:
        fail(f"A: phase 6 merge-prs.py did not run with ready PRs; trace={t!r}")
    else:
        ok("A: phase 6 merge-prs.py ran (ready PRs present)")
    if "run-post-merge.py" not in t:
        fail(f"A: phases 7-9 run-post-merge.py did not run; trace={t!r}")
    else:
        ok("A: phases 7-9 run-post-merge.py ran")
    if "update-state.py" not in t:
        fail(f"A: phase 10 update-state.py did not run; trace={t!r}")
    else:
        ok("A: phase 10 update-state.py ran")
    if "dispatch.py" in t:
        fail("A: phase 5 dispatch ran in a headless tick (must NEVER happen)")
    else:
        ok("A: phase 5 dispatch did NOT run (headless skips dispatch)")
    # Result JSON must be parseable and mark dispatch skipped.
    try:
        result = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        result = None
        fail(f"A: stdout is not a single JSON object: {proc.stdout!r}")
    if isinstance(result, dict):
        ok("A: emitted a JSON result object")
        if result.get("dispatch") not in ("skipped", "skipped-headless", False):
            fail(f"A: result does not mark dispatch skipped: {result!r}")
        else:
            ok("A: result marks dispatch skipped (no Claude)")


# ---------------------------------------------------------------------------
# Scenario B — stop marker short-circuits to a clean no-op
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    write_state(state_dir, {"queue": [], "in_flight": [], "merge_ready": [1]})
    # Plant the stop marker.
    open(os.path.join(repo_root, ".rabbit-auto-evolve-stop-requested"), "w").close()

    proc = run_tick(repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"B: stop-marker tick exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("B: stop-marker tick exited 0 (clean)")
    t = read_trace(trace)
    # The Inv 38 tick-start sync runs before the stop-check; only PHASE
    # scripts must be absent on a stop short-circuit.
    phases = [x for x in t if x != "sync-tree.py"]
    if phases:
        fail(f"B: phases ran despite stop marker; trace={t!r}")
    else:
        ok("B: no phase scripts ran (stop short-circuit)")


# ---------------------------------------------------------------------------
# Scenario C — abort marker short-circuits to a clean no-op
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    write_state(state_dir, {"queue": [], "in_flight": [], "merge_ready": [1]})
    open(os.path.join(repo_root, ".rabbit-auto-evolve-aborted"), "w").close()

    proc = run_tick(repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"C: abort-marker tick exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("C: abort-marker tick exited 0 (clean)")
    t = read_trace(trace)
    phases = [x for x in t if x != "sync-tree.py"]
    if phases:
        fail(f"C: phases ran despite abort marker; trace={t!r}")
    else:
        ok("C: no phase scripts ran (abort short-circuit)")


# ---------------------------------------------------------------------------
# Scenario D — no ready PRs: merge is skipped but fetch/plan/persist still run
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    write_state(state_dir, {
        "schema_version": "1.2.0",
        "queue": [],
        "in_flight": [],
        "merge_ready": [],
        "pending_post_merge": [],
    })

    proc = run_tick(repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"D: no-ready tick exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("D: no-ready-PR tick exited 0")
    t = read_trace(trace)
    if "fetch-queue.py" not in t:
        fail(f"D: phase 2-4 did not run; trace={t!r}")
    else:
        ok("D: phases 2-4 ran with no ready PRs")
    if "merge-prs.py" in t:
        fail(f"D: merge-prs.py ran with empty merge_ready; trace={t!r}")
    else:
        ok("D: merge-prs.py skipped (no ready PRs)")
    if "update-state.py" not in t:
        fail(f"D: phase 10 persist did not run; trace={t!r}")
    else:
        ok("D: phase 10 persist ran")
    if "dispatch.py" in t:
        fail("D: dispatch ran in a headless tick")


# ---------------------------------------------------------------------------
# Scenario E — persist runs against the REAL update-state.py and drops the
# transient `merge_ready` hint (which is NOT in the canonical Inv 9 schema and
# would otherwise be rejected as an additional property). Uses the real
# update-state.py alongside the stub fetch/triage/plan so the round-trip is
# exercised end-to-end.
# ---------------------------------------------------------------------------
import shutil  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    # Replace the update-state.py stub with the REAL script + its schema.
    real_update = os.path.join(SCRIPTS, "update-state.py")
    shutil.copy(real_update, os.path.join(script_dir, "update-state.py"))
    real_schema_dir = os.path.join(SCRIPTS, "schemas")
    if os.path.isdir(real_schema_dir):
        shutil.copytree(real_schema_dir, os.path.join(script_dir, "schemas"))
    # A fully-valid Inv 9 state PLUS the transient merge_ready hint.
    write_state(state_dir, {
        "schema_version": "1.2.0",
        "updated_at": "2026-06-03T00:00:00Z",
        "queue": [],
        "in_flight": [],
        "last_merged_sha": None,
        "last_tagged_version": None,
        "consecutive_failures": 0,
        "stop_requested": False,
        "restart_needed": None,
        "merge_ready": [],
    })

    proc = run_tick(repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"E: real-persist tick exit {proc.returncode}; "
             f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    else:
        ok("E: tick persisted through the real update-state.py (exit 0)")
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        persisted = json.load(f)
    if "merge_ready" in persisted:
        fail(f"E: persisted state still carries transient merge_ready: {persisted!r}")
    else:
        ok("E: transient merge_ready dropped from persisted state")


# ---------------------------------------------------------------------------
# Scenario F — a failing tick-start sync short-circuits to a clean no-op
# (Inv 38 / #524): the tick must NOT run stale phase scripts on a dirty or
# divergent tree. The sync-tree stub here exits non-zero.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    # Overwrite the sync stub with a failing one (exits non-zero).
    with open(os.path.join(script_dir, "sync-tree.py"), "w") as f:
        f.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys
            with open({trace!r}, "a") as _t:
                _t.write("sync-tree.py" + "\\n")
            print('{{"status": "dirty"}}')
            sys.exit(1)
            """))
    write_state(state_dir, {
        "schema_version": "1.2.0",
        "queue": [],
        "in_flight": [],
        "merge_ready": [111],
        "pending_post_merge": [],
    })

    proc = run_tick(repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"F: sync-fail tick exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("F: sync-fail tick exited 0 (clean short-circuit no-op)")
    t = read_trace(trace)
    if "sync-tree.py" not in t:
        fail(f"F: sync-tree.py did not run; trace={t!r}")
    else:
        ok("F: sync-tree.py ran")
    ran_phases = [x for x in t if x != "sync-tree.py"]
    if ran_phases:
        fail(f"F: phase scripts ran after a failed sync (stale risk); "
             f"trace={t!r}")
    else:
        ok("F: no phase scripts ran after a failed sync (Inv 38)")


# ---------------------------------------------------------------------------
# --help smoke
# ---------------------------------------------------------------------------
proc = subprocess.run([sys.executable, TICK, "--help"], capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"--help: tick-headless.py exit {proc.returncode}; stderr={proc.stderr!r}")
elif "headless" not in (proc.stdout + proc.stderr).lower():
    fail("--help: usage text missing 'headless'")
else:
    ok("--help: tick-headless.py exits 0 with recognizable usage")


sys.exit(FAIL)
