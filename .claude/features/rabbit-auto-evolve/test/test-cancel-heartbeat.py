#!/usr/bin/env python3
"""test-cancel-heartbeat.py — e2e tests for `schedule-decision.py
cancel-heartbeat` (Inv 71, issue #1168).

Follow-up to Inv 70 (#1160): a user `stop` writes
`.rabbit-auto-evolve-stop-requested` (Inv 41) and Inv 70 tears down the armed
`#refire` ONE-SHOT, but on the `CronCreate` fallback the RECURRING/durable
heartbeat (bare `/rabbit-auto-evolve tick`) is left armed and keeps firing —
each fire re-enters the SAME live session, observes the stop marker, and halts
at phase 0, burning a full live Claude turn per fire, indefinitely, until the
user runs `off`. The cost is path-asymmetric:

  - crontab path: the heartbeat is a system-cron entry firing
    `tick-headless.py` (Claude-FREE) — an empty post-stop fire is ≈free, so the
    heartbeat is NEVER disarmed (cancel_heartbeat_ids is always empty).
  - croncreate path: the heartbeat is a durable `CronCreate` entry firing a
    real `/rabbit-auto-evolve tick` (a LIVE Claude turn) — so `stop` MUST
    disarm it.

A script cannot call `CronList`/`CronDelete`, so the dispatcher runs the
disarm: `CronList`, inject the snapshot via RABBIT_AUTO_EVOLVE_CRON_LIST,
`schedule-decision.py cancel-heartbeat`, then `CronDelete` each
`cancel_heartbeat_ids` id. The scheduler is resolved via detect-scheduler.py
(probing `crontab -l` through the RABBIT_CRONTAB_CMD shim).

`cancel-heartbeat` reuses the SAME `_is_heartbeat` complement of the Inv 33/47
`is_refire_oneshot` predicate the create-path dedup uses, and emits
`{"scheduler": ..., "cancel_heartbeat_ids": [...]}`.

Scenarios (Inv 71):
  A) croncreate scheduler + snapshot mixing a durable bare-tick heartbeat with
     a pending #refire one-shot -> the heartbeat id is in cancel_heartbeat_ids,
     the refire id is NEVER (Inv 70 owns those)
  B) crontab scheduler + the SAME snapshot -> empty cancel_heartbeat_ids (the
     system-cron heartbeat is Claude-free, nothing to CronDelete)
  C) croncreate + absent snapshot (env unset) -> empty cancel_heartbeat_ids
  D) croncreate + malformed snapshot (non-JSON) -> empty cancel_heartbeat_ids
  E) croncreate + a recurring-but-not-durable heartbeat (and a durable-but-not-
     recurring heartbeat) -> BOTH ids land in cancel_heartbeat_ids
  F) exit code is 0; stdout carries both `scheduler` and `cancel_heartbeat_ids`
"""

import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
DECIDE = os.path.join(SCRIPTS, "schedule-decision.py")

REFIRE_PROMPT = "/rabbit-auto-evolve tick #refire"
HEARTBEAT_PROMPT = "/rabbit-auto-evolve tick"

pass_n = 0
fail_n = 0


def ok(msg):
    global pass_n
    pass_n += 1
    print(f"  PASS: {msg}")


def bad(msg):
    global fail_n
    fail_n += 1
    print(f"  FAIL: {msg}", file=sys.stderr)


def _make_crontab_shim(scheduler):
    """Write a fake `crontab` binary that detect-scheduler.py probes via
    RABBIT_CRONTAB_CMD. For `croncreate` it emits a permission denial; for
    `crontab` it exits 0 (usable)."""
    fd, path = tempfile.mkstemp(prefix="crontab-shim-", suffix=".sh")
    if scheduler == "croncreate":
        body = (
            "#!/bin/sh\n"
            'echo "You (test) are not allowed to use this program (crontab)" '
            ">&2\n"
            "exit 1\n"
        )
    else:
        body = "#!/bin/sh\nexit 0\n"
    with os.fdopen(fd, "w") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP
             | stat.S_IXOTH)
    return path


def run_cancel(scheduler, cron_list=None):
    """Invoke `schedule-decision.py cancel-heartbeat` with the scheduler forced
    via a RABBIT_CRONTAB_CMD shim and an optional CronList snapshot."""
    env = dict(os.environ)
    env.pop("RABBIT_AUTO_EVOLVE_CRON_LIST", None)
    env["RABBIT_CRONTAB_CMD"] = _make_crontab_shim(scheduler)
    if cron_list is not None:
        env["RABBIT_AUTO_EVOLVE_CRON_LIST"] = cron_list
    return subprocess.run(
        [sys.executable, DECIDE, "cancel-heartbeat"],
        capture_output=True, text=True, env=env,
    )


def _entry(cid, prompt, recurring=False, durable=False):
    return {"id": cid, "prompt": prompt, "recurring": recurring,
            "durable": durable}


# --- Scenario A: croncreate, heartbeat + refire -----------------------------
snapshot = json.dumps([
    _entry("hb-1", HEARTBEAT_PROMPT, recurring=True, durable=True),
    _entry("refire-1", REFIRE_PROMPT, recurring=False, durable=False),
])
proc = run_cancel("croncreate", snapshot)
if proc.returncode != 0:
    bad(f"A: cancel-heartbeat exited {proc.returncode}: {proc.stderr}")
else:
    try:
        j = json.loads(proc.stdout)
    except Exception as e:  # noqa: BLE001
        bad(f"A: stdout not JSON: {e}: {proc.stdout!r}")
        j = {}
    if j.get("scheduler") == "croncreate":
        ok("A: scheduler resolved to croncreate")
    else:
        bad(f"A: scheduler = {j.get('scheduler')!r}, expected croncreate")
    cancel_ids = j.get("cancel_heartbeat_ids")
    if cancel_ids == ["hb-1"]:
        ok("A: heartbeat id is in cancel_heartbeat_ids (croncreate disarm)")
    else:
        bad(f"A: cancel_heartbeat_ids = {cancel_ids!r}, expected ['hb-1']")
    if isinstance(cancel_ids, list) and "refire-1" not in cancel_ids:
        ok("A: refire id is NEVER in cancel_heartbeat_ids (Inv 70 owns it)")
    else:
        bad("A: refire id leaked into cancel_heartbeat_ids")

# --- Scenario B: crontab, SAME snapshot -> empty ----------------------------
proc = run_cancel("crontab", snapshot)
if proc.returncode != 0:
    bad(f"B: cancel-heartbeat exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    if j.get("scheduler") == "crontab":
        ok("B: scheduler resolved to crontab")
    else:
        bad(f"B: scheduler = {j.get('scheduler')!r}, expected crontab")
    if j.get("cancel_heartbeat_ids") == []:
        ok("B: crontab path -> empty cancel_heartbeat_ids (Claude-free, keep armed)")
    else:
        bad(f"B: cancel_heartbeat_ids = {j.get('cancel_heartbeat_ids')!r}, "
            "expected [] on crontab path")

# --- Scenario C: croncreate, absent snapshot --------------------------------
proc = run_cancel("croncreate", None)
if proc.returncode != 0:
    bad(f"C: cancel-heartbeat exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    if j.get("cancel_heartbeat_ids") == []:
        ok("C: absent snapshot -> empty cancel_heartbeat_ids (clean no-op)")
    else:
        bad(f"C: cancel_heartbeat_ids = {j.get('cancel_heartbeat_ids')!r}, "
            "expected []")

# --- Scenario D: croncreate, malformed snapshot -----------------------------
proc = run_cancel("croncreate", "not-json{{{")
if proc.returncode != 0:
    bad(f"D: cancel-heartbeat exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    if j.get("cancel_heartbeat_ids") == []:
        ok("D: malformed snapshot -> empty cancel_heartbeat_ids (clean no-op)")
    else:
        bad(f"D: cancel_heartbeat_ids = {j.get('cancel_heartbeat_ids')!r}, "
            "expected []")

# --- Scenario E: croncreate, recurring-only + durable-only heartbeats --------
snapshot = json.dumps([
    _entry("hb-recurring", HEARTBEAT_PROMPT, recurring=True, durable=False),
    _entry("hb-durable", HEARTBEAT_PROMPT, recurring=False, durable=True),
    _entry("refire-1", REFIRE_PROMPT, recurring=False, durable=False),
])
proc = run_cancel("croncreate", snapshot)
if proc.returncode != 0:
    bad(f"E: cancel-heartbeat exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    cancel_ids = j.get("cancel_heartbeat_ids") or []
    if set(cancel_ids) == {"hb-recurring", "hb-durable"}:
        ok("E: BOTH recurring-only and durable-only heartbeats disarmed")
    else:
        bad(f"E: cancel_heartbeat_ids = {cancel_ids!r}, expected "
            "hb-recurring,hb-durable")
    if "refire-1" not in cancel_ids:
        ok("E: refire untouched among heartbeats")
    else:
        bad("E: refire leaked into cancel_heartbeat_ids")

# --- Scenario F: exit code + JSON shape -------------------------------------
proc = run_cancel("croncreate", json.dumps(
    [_entry("hb-1", HEARTBEAT_PROMPT, recurring=True, durable=True)]))
if proc.returncode == 0:
    ok("F: exit code 0")
else:
    bad(f"F: exit code {proc.returncode}")
try:
    j = json.loads(proc.stdout)
    if "scheduler" in j and "cancel_heartbeat_ids" in j:
        ok("F: stdout carries both `scheduler` and `cancel_heartbeat_ids`")
    else:
        bad(f"F: missing keys in {j!r}")
except Exception as e:  # noqa: BLE001
    bad(f"F: stdout not JSON: {e}")


print(f"\n{pass_n} passed, {fail_n} failed")
sys.exit(1 if fail_n else 0)
