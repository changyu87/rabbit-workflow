#!/usr/bin/env python3
"""test-cancel-refire.py — e2e tests for `schedule-decision.py cancel-refire`
(Inv 70, issue #1160).

A user `stop` writes `.rabbit-auto-evolve-stop-requested` (Inv 41) so the NEXT
tick halts — but a pending `#refire` session-only one-shot already armed by a
prior tick's Inv 33 decision still fires, enters a fresh tick, observes the
marker, and halts, burning one live Claude session turn for a no-op. A script
cannot call `CronList`/`CronDelete`, so the dispatcher runs the cancellation:
`CronList`, inject the snapshot via RABBIT_AUTO_EVOLVE_CRON_LIST,
`schedule-decision.py cancel-refire`, then `CronDelete` each
`cancel_refire_ids` id.

`cancel-refire` reuses the EXACT `is_refire_oneshot` predicate (Inv 33/47,
#559) the create-path dedup uses, and emits
`{"cancel_refire_ids":[...], "preserve_heartbeat_ids":[...]}`.

Scenarios (Inv 70):
  A) snapshot mixing a pending #refire session-only one-shot + the durable
     bare-tick heartbeat -> the refire id is in cancel_refire_ids, the
     heartbeat id is in preserve_heartbeat_ids, and the heartbeat is NEVER in
     cancel_refire_ids
  B) snapshot with ONLY a heartbeat (recurring/durable, no marker) -> empty
     cancel_refire_ids; the heartbeat is preserved
  C) absent snapshot (env unset) -> empty cancel_refire_ids (clean no-op)
  D) malformed snapshot (non-JSON) -> empty cancel_refire_ids (clean no-op)
  E) multiple pending refires -> ALL their ids land in cancel_refire_ids
     (at-most-one is restored next tick by the create-path; the stop tears
     down every armed refire)
  F) exit code is 0 and stdout is the JSON object
"""

import json
import os
import subprocess
import sys

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


def run_cancel(cron_list=None):
    """Invoke `schedule-decision.py cancel-refire`, optionally injecting a
    CronList snapshot through RABBIT_AUTO_EVOLVE_CRON_LIST."""
    env = dict(os.environ)
    # Isolate from any real state dir so the tick-log append never touches the
    # repo's .rabbit (cancel-refire performs no scheduling decision anyway).
    env.pop("RABBIT_AUTO_EVOLVE_CRON_LIST", None)
    if cron_list is not None:
        env["RABBIT_AUTO_EVOLVE_CRON_LIST"] = cron_list
    return subprocess.run(
        [sys.executable, DECIDE, "cancel-refire"],
        capture_output=True, text=True, env=env,
    )


def _entry(cid, prompt, recurring=False, durable=False):
    return {"id": cid, "prompt": prompt, "recurring": recurring,
            "durable": durable}


# --- Scenario A: refire + heartbeat -----------------------------------------
snapshot = json.dumps([
    _entry("refire-1", REFIRE_PROMPT, recurring=False, durable=False),
    _entry("hb-1", HEARTBEAT_PROMPT, recurring=True, durable=True),
])
proc = run_cancel(snapshot)
if proc.returncode != 0:
    bad(f"A: cancel-refire exited {proc.returncode}: {proc.stderr}")
else:
    try:
        j = json.loads(proc.stdout)
    except Exception as e:  # noqa: BLE001
        bad(f"A: stdout not JSON: {e}: {proc.stdout!r}")
        j = {}
    cancel_ids = j.get("cancel_refire_ids")
    preserve_ids = j.get("preserve_heartbeat_ids")
    if cancel_ids == ["refire-1"]:
        ok("A: pending #refire id is in cancel_refire_ids")
    else:
        bad(f"A: cancel_refire_ids = {cancel_ids!r}, expected ['refire-1']")
    if isinstance(preserve_ids, list) and "hb-1" in preserve_ids:
        ok("A: heartbeat id is in preserve_heartbeat_ids")
    else:
        bad(f"A: preserve_heartbeat_ids = {preserve_ids!r}, expected ['hb-1']")
    if isinstance(cancel_ids, list) and "hb-1" not in cancel_ids:
        ok("A: heartbeat id is NEVER in cancel_refire_ids (Inv 47)")
    else:
        bad("A: heartbeat id leaked into cancel_refire_ids (Inv 47 violation)")

# --- Scenario B: heartbeat only ---------------------------------------------
snapshot = json.dumps([
    _entry("hb-1", HEARTBEAT_PROMPT, recurring=True, durable=True),
])
proc = run_cancel(snapshot)
if proc.returncode != 0:
    bad(f"B: cancel-refire exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    if j.get("cancel_refire_ids") == []:
        ok("B: heartbeat-only snapshot -> empty cancel_refire_ids")
    else:
        bad(f"B: cancel_refire_ids = {j.get('cancel_refire_ids')!r}, expected []")
    if "hb-1" in (j.get("preserve_heartbeat_ids") or []):
        ok("B: heartbeat preserved")
    else:
        bad("B: heartbeat not preserved")

# --- Scenario C: absent snapshot --------------------------------------------
proc = run_cancel(None)
if proc.returncode != 0:
    bad(f"C: cancel-refire exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    if j.get("cancel_refire_ids") == []:
        ok("C: absent snapshot -> empty cancel_refire_ids (clean no-op)")
    else:
        bad(f"C: cancel_refire_ids = {j.get('cancel_refire_ids')!r}, expected []")

# --- Scenario D: malformed snapshot -----------------------------------------
proc = run_cancel("not-json{{{")
if proc.returncode != 0:
    bad(f"D: cancel-refire exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    if j.get("cancel_refire_ids") == []:
        ok("D: malformed snapshot -> empty cancel_refire_ids (clean no-op)")
    else:
        bad(f"D: cancel_refire_ids = {j.get('cancel_refire_ids')!r}, expected []")

# --- Scenario E: multiple pending refires -----------------------------------
snapshot = json.dumps([
    _entry("refire-1", REFIRE_PROMPT, recurring=False, durable=False),
    _entry("refire-2", REFIRE_PROMPT, recurring=False, durable=False),
    _entry("hb-1", HEARTBEAT_PROMPT, recurring=True, durable=True),
])
proc = run_cancel(snapshot)
if proc.returncode != 0:
    bad(f"E: cancel-refire exited {proc.returncode}: {proc.stderr}")
else:
    j = json.loads(proc.stdout)
    cancel_ids = j.get("cancel_refire_ids") or []
    if set(cancel_ids) == {"refire-1", "refire-2"}:
        ok("E: ALL pending refire ids land in cancel_refire_ids")
    else:
        bad(f"E: cancel_refire_ids = {cancel_ids!r}, expected refire-1,refire-2")
    if "hb-1" not in cancel_ids:
        ok("E: heartbeat untouched among multiple refires")
    else:
        bad("E: heartbeat leaked into cancel_refire_ids")

# --- Scenario F: exit code + JSON shape -------------------------------------
proc = run_cancel(json.dumps([_entry("refire-1", REFIRE_PROMPT)]))
if proc.returncode == 0:
    ok("F: exit code 0")
else:
    bad(f"F: exit code {proc.returncode}")
try:
    j = json.loads(proc.stdout)
    if "cancel_refire_ids" in j and "preserve_heartbeat_ids" in j:
        ok("F: stdout is the JSON object with both keys")
    else:
        bad(f"F: missing keys in {j!r}")
except Exception as e:  # noqa: BLE001
    bad(f"F: stdout not JSON: {e}")


print(f"\n{pass_n} passed, {fail_n} failed")
sys.exit(1 if fail_n else 0)
