#!/usr/bin/env python3
"""test-run-tick-phases.py — e2e tests for scripts/run-tick-phases.py (Inv 40 /
issue #513: the single shared scripted phase-walk both the headless tick and
the in-session tick invoke).

run-tick-phases.py owns the deterministic phase-walk in TWO segments:

  - `pre-dispatch`  — tick-start sync, phase 0/1 stop/abort short-circuit,
                      running-guard, phases 2-4 (fetch | triage | plan).
  - `post-dispatch` — phase 6 (merge ready PRs), phases 7-9 (run-post-merge),
                      phase 10 (persist: re-read on-disk state, drop the
                      transient `merge_ready` hint, pipe through
                      update-state.py).

Phase 5 (dispatch) is NEVER inside this script — it is the ONLY phase the
in-session path adds between the two segments, and it needs Claude. The
headless tick chains pre-dispatch -> (skip dispatch) -> post-dispatch; the
in-session tick chains pre-dispatch -> Phase 5 (Claude) -> post-dispatch.

Tests are hermetic: RABBIT_AUTO_EVOLVE_SCRIPT_DIR points at a tempdir of STUB
phase scripts that each append their name to a trace file and emit minimal
valid output. Phase 10 persist is exercised against the REAL update-state.py
so the re-read / drop-merge_ready round-trip is end-to-end.
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

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


STUBS = {
    "sync-tree.py": "print('{\"status\": \"synced\"}')",
    "running-guard.py": "print('{\"action\": \"proceed\"}')",
    "fetch-queue.py": "print('[]')",
    "triage-batch.py": "import sys; sys.stdin.read(); print('[]')",
    "plan-batch.py": "import sys; sys.stdin.read(); print('{}')",
    "merge-prs.py": "print('[]')",
    "run-post-merge.py": "print('{\"status\": \"noop\", \"pending\": []}')",
    # update-state replaced with the REAL script by tests that need persist.
    "update-state.py": "import sys; sys.stdin.read(); print('{\"ok\": true}')",
    "dispatch.py": "print('DISPATCH RAN')",
}


def make_stub_scripts(dirpath, trace_file, overrides=None):
    bodies = dict(STUBS)
    if overrides:
        bodies.update(overrides)
    for name, body in bodies.items():
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


def install_real_update_state(script_dir):
    shutil.copy(os.path.join(SCRIPTS, "update-state.py"),
                os.path.join(script_dir, "update-state.py"))
    schemas = os.path.join(SCRIPTS, "schemas")
    dst_schemas = os.path.join(script_dir, "schemas")
    if os.path.isdir(schemas) and not os.path.isdir(dst_schemas):
        shutil.copytree(schemas, dst_schemas)


def run_segment(segment, repo_root, script_dir, state_dir, trace):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, WALK, segment],
        cwd=repo_root, capture_output=True, text=True, env=env,
    )


def read_trace(trace):
    if not os.path.isfile(trace):
        return []
    with open(trace) as f:
        return [ln.strip() for ln in f if ln.strip()]


def write_state(state_dir, mapping):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(mapping, f, indent=2)


def fresh(d, overrides=None):
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace, overrides)
    return repo_root, state_dir, script_dir, trace


VALID_STATE = {
    "schema_version": "1.2.0",
    "updated_at": "2026-06-03T00:00:00Z",
    "queue": [],
    "in_flight": [],
    "last_merged_sha": None,
    "last_tagged_version": None,
    "consecutive_failures": 0,
    "stop_requested": False,
    "restart_needed": None,
}


# ---------------------------------------------------------------------------
# A — pre-dispatch segment runs sync + phases 2-4; never runs merge/persist.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir, trace = fresh(d)
    write_state(state_dir, dict(VALID_STATE, merge_ready=[111]))
    proc = run_segment("pre-dispatch", repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"A: pre-dispatch exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("A: pre-dispatch exited 0")
    t = read_trace(trace)
    if t[:1] != ["sync-tree.py"]:
        fail(f"A: sync-tree.py did not run first; trace={t!r}")
    else:
        ok("A: pre-dispatch ran sync-tree.py first (Inv 38)")
    for phase in ("fetch-queue.py", "triage-batch.py", "plan-batch.py"):
        if phase not in t:
            fail(f"A: pre-dispatch missing {phase}; trace={t!r}")
        else:
            ok(f"A: pre-dispatch ran {phase}")
    for forbidden in ("merge-prs.py", "run-post-merge.py", "update-state.py",
                      "dispatch.py"):
        if forbidden in t:
            fail(f"A: pre-dispatch ran {forbidden} (out of segment); trace={t!r}")
    ok("A: pre-dispatch did not run merge/post-merge/persist/dispatch")
    try:
        res = json.loads(proc.stdout)
        if res.get("action") != "proceed":
            fail(f"A: pre-dispatch result not 'proceed': {res!r}")
        else:
            ok("A: pre-dispatch result signals proceed")
    except (ValueError, json.JSONDecodeError):
        fail(f"A: pre-dispatch stdout not JSON: {proc.stdout!r}")


# ---------------------------------------------------------------------------
# B — pre-dispatch short-circuits on the stop marker (no phase scripts run).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir, trace = fresh(d)
    write_state(state_dir, dict(VALID_STATE))
    open(os.path.join(repo_root, ".rabbit-auto-evolve-stop-requested"), "w").close()
    proc = run_segment("pre-dispatch", repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"B: stop short-circuit exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("B: stop short-circuit exited 0")
    t = [x for x in read_trace(trace) if x != "sync-tree.py"]
    if t:
        fail(f"B: phase scripts ran despite stop marker; trace={t!r}")
    else:
        ok("B: no phase scripts ran on stop short-circuit")
    res = json.loads(proc.stdout)
    if res.get("action") != "skip":
        fail(f"B: stop result not 'skip': {res!r}")
    else:
        ok("B: stop result signals skip")


# ---------------------------------------------------------------------------
# C — pre-dispatch honors the running-guard skip verdict.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir, trace = fresh(d, overrides={
        "running-guard.py": "print('{\"action\": \"skip\", \"reason\": \"tick-running\"}')",
    })
    write_state(state_dir, dict(VALID_STATE))
    proc = run_segment("pre-dispatch", repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"C: guard-skip exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("C: guard-skip exited 0")
    t = read_trace(trace)
    if "fetch-queue.py" in t:
        fail(f"C: phases ran despite running-guard skip; trace={t!r}")
    else:
        ok("C: phases 2-4 did not run on running-guard skip")
    res = json.loads(proc.stdout)
    if res.get("action") != "skip":
        fail(f"C: guard-skip result not 'skip': {res!r}")
    else:
        ok("C: guard-skip result signals skip")


# ---------------------------------------------------------------------------
# D — post-dispatch runs merge (ready PRs) + post-merge + persist; drops the
# transient merge_ready against the REAL update-state.py.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir, trace = fresh(d)
    install_real_update_state(script_dir)
    write_state(state_dir, dict(VALID_STATE, merge_ready=[111, 222]))
    proc = run_segment("post-dispatch", repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"D: post-dispatch exit {proc.returncode}; "
             f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    else:
        ok("D: post-dispatch exited 0")
    t = read_trace(trace)
    if "merge-prs.py" not in t:
        fail(f"D: phase 6 merge-prs.py did not run with ready PRs; trace={t!r}")
    else:
        ok("D: phase 6 merge-prs.py ran")
    if "run-post-merge.py" not in t:
        fail(f"D: phases 7-9 run-post-merge.py did not run; trace={t!r}")
    else:
        ok("D: phases 7-9 run-post-merge.py ran")
    # Phase 10 persist runs the REAL update-state.py (which does not write to
    # the trace file); its effect is verified below by the dropped merge_ready.
    if "dispatch.py" in t:
        fail("D: dispatch ran inside the shared phase-walk (must never happen)")
    else:
        ok("D: dispatch did NOT run inside the shared phase-walk")
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        persisted = json.load(f)
    if "merge_ready" in persisted:
        fail(f"D: persisted state still carries merge_ready: {persisted!r}")
    else:
        ok("D: transient merge_ready dropped from persisted state")


# ---------------------------------------------------------------------------
# E — post-dispatch skips merge when there are no ready PRs, still persists.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir, trace = fresh(d)
    install_real_update_state(script_dir)
    write_state(state_dir, dict(VALID_STATE, merge_ready=[]))
    proc = run_segment("post-dispatch", repo_root, script_dir, state_dir, trace)
    if proc.returncode != 0:
        fail(f"E: no-ready post-dispatch exit {proc.returncode}; stderr={proc.stderr!r}")
    else:
        ok("E: no-ready post-dispatch exited 0")
    t = read_trace(trace)
    if "merge-prs.py" in t:
        fail(f"E: merge-prs.py ran with empty merge_ready; trace={t!r}")
    else:
        ok("E: merge-prs.py skipped (no ready PRs)")
    # Phase 10 persist re-persists via the REAL update-state.py: the state file
    # remains present and valid (re-read -> validate -> atomic write).
    with open(os.path.join(state_dir, "auto-evolve-state.json")) as f:
        repersisted = json.load(f)
    if repersisted.get("schema_version") != "1.2.0":
        fail(f"E: phase 10 persist did not re-persist a valid state: {repersisted!r}")
    else:
        ok("E: phase 10 persist re-persisted a valid state")


# ---------------------------------------------------------------------------
# F — --help smoke for both segments.
# ---------------------------------------------------------------------------
proc = subprocess.run([sys.executable, WALK, "--help"], capture_output=True, text=True)
if proc.returncode != 0:
    fail(f"--help: run-tick-phases.py exit {proc.returncode}; stderr={proc.stderr!r}")
elif "phase" not in (proc.stdout + proc.stderr).lower():
    fail("--help: usage text missing 'phase'")
else:
    ok("--help: run-tick-phases.py exits 0 with recognizable usage")


sys.exit(FAIL)
