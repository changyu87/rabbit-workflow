#!/usr/bin/env python3
"""test-tick-jitter-compute-wired.py — e2e tests for the Inv 56 jitter-compute
wiring (issue #959).

Before #959 the empirical jitter artifact `auto-evolve-tick-jitter.json` was
read by banner-status.py but NEVER written by any tick path — nothing invoked
`tick-jitter.py compute` within the feature. The artifact never materialized, so
banner-status.py always fell back to the cold-start bound
`min(15, ceil(period_minutes * 0.10))` = 3 min for the 30-min `13,43` heartbeat,
while the real fire offset is ~13 min — the banner ETA rendered a constant ~10
min EARLIER than the tick actually fired.

The fix wires `tick-jitter.py compute` into the shared scripted phase-walk
(`run-tick-phases.py` `post-dispatch` segment), which runs on BOTH the headless
and the in-session tick paths, so the artifact is refreshed every tick. These
tests drive the REAL run-tick-phases.py post-dispatch segment (with a mocked
tick.log fire history and the real tick-jitter.py / banner-status.py) and assert:

  - after post-dispatch, `auto-evolve-tick-jitter.json` exists with the EMPIRICAL
    offset (median of boundary->fire deltas, +13 for the mocked 13,43 history),
    NOT the 3-min cold-start fallback;
  - banner-status.py then renders the idle next-tick ETA at boundary + that
    empirical offset (i.e. the +13 fire time, not the +3 cold-start time);
  - a jitter-compute failure NEVER fails the tick (hygiene-step contract,
    mirroring the Inv 49 sweep / Inv 55 reconcile).

The post-dispatch segment is exercised with STUB phase scripts for the unrelated
phases (merge / post-merge / reconcile) but the REAL update-state.py and the REAL
tick-jitter.py, so the compute wiring is end-to-end.
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
BANNER = os.path.join(SCRIPTS, "banner-status.py")

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# Minimal stubs for the post-dispatch phases unrelated to jitter compute.
STUBS = {
    "sync-tree.py": "print('{\"status\": \"synced\"}')",
    "clean-dispatch-leaks.py": "print('{\"status\": \"clean\"}')",
    "merge-prs.py": "print('[]')",
    "run-post-merge.py": "print('{\"status\": \"noop\", \"pending\": []}')",
    "reconcile-labels.py": "print('{\"status\": \"reconciled\"}')",
}

# Real scripts copied into the stub dir (the compute wiring must use the real
# tick-jitter.py and the real update-state.py round-trip).
REAL_SCRIPTS = ["tick-jitter.py", "update-state.py"]


def make_stub_scripts(dirpath, overrides=None):
    bodies = dict(STUBS)
    if overrides:
        bodies.update(overrides)
    for name, body in bodies.items():
        path = os.path.join(dirpath, name)
        with open(path, "w") as f:
            f.write(textwrap.dedent(f"""\
                #!{sys.executable}
                {body}
                """))
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    for name in REAL_SCRIPTS:
        if overrides and name in overrides:
            continue
        shutil.copy(os.path.join(SCRIPTS, name), os.path.join(dirpath, name))
    schemas = os.path.join(SCRIPTS, "schemas")
    dst_schemas = os.path.join(dirpath, "schemas")
    if os.path.isdir(schemas) and not os.path.isdir(dst_schemas):
        shutil.copytree(schemas, dst_schemas)


# A 30-min `13,43` heartbeat with every fire +13 min late (the empirical
# constant from #881/#959). Each line is a tick.log fire record (Inv 36).
HEARTBEAT_CRON = "13,43 * * * *"
FIRE_TIMES = [
    "2026-06-04T21:56:00Z",  # boundary 21:43 + 13
    "2026-06-04T22:26:00Z",  # boundary 22:13 + 13
    "2026-06-04T22:56:00Z",  # boundary 22:43 + 13
    "2026-06-04T23:26:00Z",  # boundary 23:13 + 13
]
EXPECTED_OFFSET = 13
COLD_START_FALLBACK = 3  # min(15, ceil(30 * 0.10))

VALID_STATE = {
    "schema_version": "1.4.0",
    "updated_at": "2026-06-03T00:00:00Z",
    "queue": [],
    "last_merged_sha": None,
    "last_tagged_version": None,
    "consecutive_failures": 0,
    "stop_requested": False,
    "restart_needed": None,
}


def write_scheduled_tasks(repo_root, cron):
    path = os.path.join(repo_root, ".claude", "scheduled_tasks.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(
            {"tasks": [{"cron": cron,
                        "prompt": "/rabbit-auto-evolve tick"}]},
            f,
        )


def write_tick_log(state_dir, fire_times):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "tick.log"), "w") as f:
        for ts in fire_times:
            f.write(json.dumps({"ts": ts, "decision": "fire"}) + "\n")


def write_state(state_dir, mapping):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "auto-evolve-state.json"), "w") as f:
        json.dump(mapping, f, indent=2)


def run_post_dispatch(repo_root, script_dir, state_dir):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_SCRIPT_DIR"] = script_dir
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = state_dir
    return subprocess.run(
        [sys.executable, WALK, "post-dispatch"],
        cwd=repo_root, capture_output=True, text=True, env=env,
    )


def run_banner(repo_root, now_iso):
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = repo_root
    env["RABBIT_AUTO_EVOLVE_NOW"] = now_iso
    return subprocess.run(
        [sys.executable, BANNER],
        cwd=repo_root, capture_output=True, text=True, env=env,
    )


def fresh(d, overrides=None):
    repo_root = os.path.join(d, "repo")
    state_dir = os.path.join(repo_root, ".rabbit")
    script_dir = os.path.join(d, "stubs")
    os.makedirs(repo_root)
    os.makedirs(script_dir)
    make_stub_scripts(script_dir, overrides)
    return repo_root, state_dir, script_dir


# ---------------------------------------------------------------------------
# A — post-dispatch writes the jitter artifact with the EMPIRICAL offset from
#     the mocked tick.log fire history (not the cold-start fallback).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir = fresh(d)
    write_scheduled_tasks(repo_root, HEARTBEAT_CRON)
    write_tick_log(state_dir, FIRE_TIMES)
    write_state(state_dir, dict(VALID_STATE))

    artifact = os.path.join(state_dir, "auto-evolve-tick-jitter.json")
    if os.path.exists(artifact):
        fail("A: artifact pre-existed before the tick (setup bug)")

    proc = run_post_dispatch(repo_root, script_dir, state_dir)
    if proc.returncode != 0:
        fail(f"A: post-dispatch exit {proc.returncode}; "
             f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
    else:
        ok("A: post-dispatch exited 0")

    if not os.path.exists(artifact):
        fail("A: jitter artifact NOT written by the tick "
             "(tick-jitter.py compute was never wired into the walk)")
    else:
        ok("A: jitter artifact written by the tick")
        with open(artifact) as f:
            rec = json.load(f)
        if rec.get("observed_jitter_minutes") != EXPECTED_OFFSET:
            fail(f"A: artifact offset = {rec.get('observed_jitter_minutes')!r}, "
                 f"expected empirical {EXPECTED_OFFSET}")
        else:
            ok(f"A: artifact offset is the empirical +{EXPECTED_OFFSET}")
        if rec.get("cold_start") is not False:
            fail(f"A: artifact cold_start = {rec.get('cold_start')!r}, "
                 "expected False (empirical history present)")
        else:
            ok("A: artifact marked empirical (cold_start False)")


# ---------------------------------------------------------------------------
# B — after the tick, banner-status.py renders the idle ETA at boundary + the
#     EMPIRICAL +13 offset, not the +3 cold-start fallback.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir = fresh(d)
    write_scheduled_tasks(repo_root, HEARTBEAT_CRON)
    write_tick_log(state_dir, FIRE_TIMES)
    write_state(state_dir, dict(VALID_STATE))

    # The active + started-then-idle banner branch (state file present, no
    # priority markers) is the only one that carries an ETA.
    open(os.path.join(repo_root, ".rabbit-auto-evolve-active"), "w").close()

    proc = run_post_dispatch(repo_root, script_dir, state_dir)
    if proc.returncode != 0:
        fail(f"B: post-dispatch exit {proc.returncode}; stderr={proc.stderr!r}")

    # now=14:20 -> next boundary is 14:43; empirical fire is 14:43 + 13 = 14:56;
    # cold-start fallback would render 14:43 + 3 = 14:46 (the buggy ~10-min-early).
    banner = run_banner(repo_root, "2026-06-04T14:20:00")
    if banner.returncode != 0:
        fail(f"B: banner exit {banner.returncode}; stderr={banner.stderr!r}")
    out = json.loads(banner.stdout)
    line2 = (out.get("line2") or {}).get("text", "")
    if "next tick 14:56" in line2:
        ok("B: banner ETA is the empirical fire time 14:56 (+13)")
    else:
        fail(f"B: banner ETA is not the empirical 14:56; line2={line2!r}")
    if "next tick 14:46" in line2:
        fail(f"B: banner still renders the +3 cold-start ETA 14:46; "
             f"line2={line2!r}")
    else:
        ok("B: banner no longer renders the +3 cold-start ETA")


# ---------------------------------------------------------------------------
# C — a jitter-compute failure NEVER fails the tick (hygiene-step contract).
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    repo_root, state_dir, script_dir = fresh(
        d, overrides={"tick-jitter.py": "import sys; sys.exit(3)"})
    write_scheduled_tasks(repo_root, HEARTBEAT_CRON)
    write_tick_log(state_dir, FIRE_TIMES)
    write_state(state_dir, dict(VALID_STATE))

    proc = run_post_dispatch(repo_root, script_dir, state_dir)
    if proc.returncode != 0:
        fail(f"C: jitter-compute failure FAILED the tick (exit "
             f"{proc.returncode}); a hygiene step must never fail the tick. "
             f"stderr={proc.stderr!r}")
    else:
        ok("C: jitter-compute failure did not fail the tick")
    try:
        res = json.loads(proc.stdout)
        if res.get("status") == "failed":
            fail(f"C: tick status 'failed' on jitter-compute error: {res!r}")
        else:
            ok("C: tick status not 'failed' on jitter-compute error")
    except (ValueError, json.JSONDecodeError):
        fail(f"C: post-dispatch stdout not JSON: {proc.stdout!r}")


sys.exit(FAIL)
