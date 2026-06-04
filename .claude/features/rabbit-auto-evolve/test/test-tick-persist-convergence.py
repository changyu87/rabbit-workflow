#!/usr/bin/env python3
"""test-tick-persist-convergence.py — regression test for Inv 40 / issue #513.

The in-session tick MUST persist BYTE-IDENTICAL state to what the headless
tick produces for the SAME on-disk phase-script mutations. Both paths walk
ONE shared scripted phase-walk (`run-tick-phases.py`); the in-session path
differs ONLY by inserting Phase 5 (dispatch) between the two segments. Phase 5
mutates nothing the persist step reads (the phase scripts mutate on-disk state;
dispatch produces a PR, not loop state), so the persisted bytes must match.

This test simulates BOTH paths against identical on-disk state + identical
STUB phase scripts (which deterministically mutate the on-disk state to model
what merge-prs.py / run-post-merge.py do), then asserts the persisted
auto-evolve-state.json bytes are identical:

  headless path:    pre-dispatch -> (skip dispatch) -> post-dispatch
  in-session path:  pre-dispatch -> [Phase 5 = no state mutation] -> post-dispatch

The persist step (phase 10) re-reads the on-disk state, drops the transient
`merge_ready`, and pipes through the REAL update-state.py in BOTH paths — no
LLM hand-assembly of the new-state object anywhere.
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
HEADLESS = os.path.join(SCRIPTS, "tick-headless.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# Stub phase scripts. run-post-merge.py here MUTATES the on-disk state file
# (model: it clears pending_post_merge and bumps last_merged_sha) exactly as a
# real phase script would, so the persist step has something to re-read.
STUBS = {
    "sync-tree.py": "print('{\"status\": \"synced\"}')",
    "running-guard.py": "print('{\"action\": \"proceed\"}')",
    "fetch-queue.py": "print('[]')",
    "triage-batch.py": "import sys; sys.stdin.read(); print('[]')",
    "plan-batch.py": "import sys; sys.stdin.read(); print('{}')",
    "clean-dispatch-leaks.py": "print('{\"status\": \"clean\"}')",
    "merge-prs.py": "print('[]')",
    # mutate on-disk state to model a real post-merge drain.
    "run-post-merge.py": textwrap.dedent("""\
        import json, os
        sd = os.environ["RABBIT_AUTO_EVOLVE_STATE_DIR"]
        p = os.path.join(sd, "auto-evolve-state.json")
        with open(p) as f:
            s = json.load(f)
        s["pending_post_merge"] = []
        s["last_merged_sha"] = "deadbeefcafe"
        s["last_tagged_version"] = "v9.9.9"
        with open(p, "w") as f:
            json.dump(s, f, indent=2)
        print('{"status": "drained"}')
    """),
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
                """) + body + "\n")
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    # real update-state.py + schema for the persist round-trip.
    shutil.copy(os.path.join(SCRIPTS, "update-state.py"),
                os.path.join(dirpath, "update-state.py"))
    schemas = os.path.join(SCRIPTS, "schemas")
    dst_schemas = os.path.join(dirpath, "schemas")
    if os.path.isdir(schemas) and not os.path.isdir(dst_schemas):
        shutil.copytree(schemas, dst_schemas)


INITIAL_STATE = {
    "schema_version": "1.3.0",
    "updated_at": "2026-06-03T00:00:00Z",
    "queue": [],
    "in_flight": [],
    "last_merged_sha": None,
    "last_tagged_version": None,
    "consecutive_failures": 0,
    "stop_requested": False,
    "restart_needed": None,
    "pending_post_merge": [333],
    "merge_ready": [333],
}


def env_for(repo_root, script_dir, state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return env


def setup(d):
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    trace = os.path.join(d, "trace.txt")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, trace)
    os.makedirs(state_dir)
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(INITIAL_STATE, f, indent=2)
    return repo_root, state_dir, script_dir, trace


def persisted_bytes(state_dir):
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "rb") as f:
        return f.read()


# --- headless path: tick-headless.py runs the full deterministic walk -------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir, trace = setup(d)
    proc = subprocess.run([sys.executable, HEADLESS], cwd=repo_root,
                          capture_output=True, text=True,
                          env=env_for(repo_root, script_dir, state_dir))
    if proc.returncode != 0:
        fail(f"headless tick exit {proc.returncode}; stderr={proc.stderr!r}")
    headless_bytes = persisted_bytes(state_dir)
    headless_obj = json.loads(headless_bytes)
    ok("headless path persisted state")

# --- in-session path: pre-dispatch -> (Phase 5 no-op) -> post-dispatch ------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir, trace = setup(d)
    env = env_for(repo_root, script_dir, state_dir)
    pre = subprocess.run([sys.executable, WALK, "pre-dispatch"], cwd=repo_root,
                         capture_output=True, text=True, env=env)
    if pre.returncode != 0:
        fail(f"in-session pre-dispatch exit {pre.returncode}; stderr={pre.stderr!r}")
    # Phase 5 (dispatch) happens here in the live session; it mutates NO loop
    # state (it produces a PR). Simulated by doing nothing.
    post = subprocess.run([sys.executable, WALK, "post-dispatch"], cwd=repo_root,
                          capture_output=True, text=True, env=env)
    if post.returncode != 0:
        fail(f"in-session post-dispatch exit {post.returncode}; stderr={post.stderr!r}")
    session_bytes = persisted_bytes(state_dir)
    ok("in-session path persisted state")

# --- the load-bearing assertion: byte-identical persisted state -------------
if "headless_bytes" in dir() and "session_bytes" in dir():
    if headless_bytes != session_bytes:
        fail("persisted state differs between headless and in-session paths\n"
             f"  headless: {headless_bytes!r}\n"
             f"  session : {session_bytes!r}")
    else:
        ok("in-session tick persists BYTE-IDENTICAL state to the headless tick")
    # And the persisted state reflects the on-disk phase mutations, not the
    # initial state (proves the persist re-reads from disk, never hand-builds).
    if headless_obj.get("last_merged_sha") != "deadbeefcafe":
        fail(f"persist did not re-read on-disk phase mutations: {headless_obj!r}")
    else:
        ok("persisted state reflects on-disk phase-script mutations (re-read, not hand-built)")
    if "merge_ready" in headless_obj:
        fail("persisted state still carries the transient merge_ready hint")
    else:
        ok("transient merge_ready dropped in both paths")


sys.exit(FAIL)
