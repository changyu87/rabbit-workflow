#!/usr/bin/env python3
"""test-schedule-decision.py — e2e tests for scripts/schedule-decision.py
(Inv 33 / D1, issue #521).

`schedule-decision.py` determines open-work presence AUTHORITATIVELY by
invoking the EXISTING `fetch-queue.py` and counting items, reads the
scheduler mechanism from `detect-scheduler.py`, logs the decision via
`tick-log.py`, and emits JSON:
  - queue non-empty -> {"decision":"immediate-refire", ...}
  - queue empty     -> {"decision":"idle", "detail":"rely on heartbeat"}

The test injects a fake `fetch-queue.py` via the
`RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD` override (a tiny program emitting a
canned JSON array) so no `gh` call is made, and a `RABBIT_CRONTAB_CMD`
crontab shim so scheduler detection is deterministic.

Scenarios:
  A) non-empty queue + usable crontab    -> immediate-refire, scheduler crontab
  B) non-empty queue + restricted crontab-> immediate-refire, scheduler
     croncreate, with a croncreate one-shot param block whose cron is a PINNED
     "M H * * *" expression (NOT "*/1 * * * *"), minute not in {0,30}, and
     recurring/durable both False (Inv 33 pinned-minute amendment, #531)
  C) empty queue                          -> idle
  D) the decision is logged to .rabbit/tick.log
  E) --help smoke
  F) _pinned_oneshot_cron(now=...) unit tests, including the :00/:30 nudge
     cases (Inv 33 pinned-minute amendment, #531)
  G) the emitted refire one-shot carries the #refire marker so it is
     distinguishable from the recurring heartbeat (Inv 33, #559)
  H) dedup decision from an injected CronList snapshot (env
     RABBIT_AUTO_EVOLVE_CRON_LIST): a prior refire + the heartbeat ->
     delete_refire_ids holds the prior refire, preserve_heartbeat_ids holds
     the heartbeat (and it is NEVER in delete_refire_ids), exactly one
     create_refire (Inv 33, #559); absent snapshot -> empty delete list
  I) is_refire_oneshot(entry) pure-predicate unit tests: a marked
     non-recurring one-shot is a refire; the recurring/durable heartbeat is
     NOT; a marker on a recurring entry is NOT; an unmarked one-shot is NOT
     (Inv 33, #559)
  J) arm-time minute-boundary skid robustness (Inv 33, #748): for every
     near-boundary decision-time clock the pinned minute is at least a
     2-minute buffer ahead (so the dispatcher's CronList->CronDelete->
     CronCreate dedup round-trip cannot cross the minute boundary and park the
     one-shot ~24h out); the emitted cron stays a valid pinned 'M H * * *' and
     the #refire marker + durable/recurring=false flags are preserved
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
DECIDE = os.path.join(SCRIPTS, "schedule-decision.py")

# A pinned one-shot cron is "M H * * *" — a specific minute and hour, never the
# fragile every-minute "*/1 * * * *". Minute must never land on :00 or :30.
PINNED_RE = re.compile(r"^\d+ \d+ \* \* \*$")


def _load_decide_module():
    spec = importlib.util.spec_from_file_location("schedule_decision", DECIDE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


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
        body = (
            'import sys\n'
            'sys.stderr.write("You (t) are not allowed to use this '
            'program (crontab)\\n")\nsys.exit(1)\n'
        )
    else:
        body = 'import sys\nsys.exit(0)\n'
    with open(shim, "w") as f:
        f.write(f"#!{sys.executable}\n" + body)
    os.chmod(shim, 0o755)
    return shim


def run(d, queue_json, restricted=False, cron_list=None):
    fetch = make_fetch_shim(d, queue_json)
    cron = make_crontab_shim(d, restricted)
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_FETCH_QUEUE_CMD"] = fetch
    env["RABBIT_CRONTAB_CMD"] = cron
    env["RABBIT_AUTO_EVOLVE_STATE_DIR"] = os.path.join(d, ".rabbit")
    if cron_list is not None:
        env["RABBIT_AUTO_EVOLVE_CRON_LIST"] = cron_list
    return subprocess.run(
        [sys.executable, DECIDE], capture_output=True, text=True, env=env,
    )


def parsed(proc):
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


NONEMPTY = '[{"number": 1, "title": "x", "labels": []}]'
EMPTY = "[]"

# A — non-empty + usable crontab
with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=False)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("decision") == "immediate-refire" \
            and j.get("scheduler") == "crontab":
        ok("A: non-empty + crontab -> immediate-refire, scheduler crontab")
    else:
        fail(f"A: out={proc.stdout!r} err={proc.stderr!r}")
    # The MACHINE wake-up fires the INTERNAL `tick` (which respects but never
    # deletes the stop marker), NOT the USER-intent `start` (which clears the
    # stop and resurrects a halted loop). See Inv 41. Per Inv 33 (#559) the
    # refire prompt ALSO carries the #refire marker so it is distinguishable
    # from the recurring heartbeat (whose prompt is the bare tick command).
    prompt = (j or {}).get("prompt", "")
    if prompt.startswith("/rabbit-auto-evolve tick") and "start" not in prompt \
            and "#refire" in prompt:
        ok("A: refire prompt is the internal tick carrying the #refire marker")
    else:
        fail(f"A: wrong/absent prompt: {j!r}")

# B — non-empty + restricted crontab
with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=True)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("decision") == "immediate-refire" \
            and j.get("scheduler") == "croncreate":
        ok("B: non-empty + restricted -> immediate-refire, scheduler croncreate")
    else:
        fail(f"B: out={proc.stdout!r} err={proc.stderr!r}")
    cc = (j or {}).get("croncreate")
    # Inv 33 (#559): the croncreate prompt fires the internal tick and carries
    # the #refire marker (distinguishing it from the recurring heartbeat).
    if isinstance(cc, dict) \
            and (cc.get("prompt") or "").startswith("/rabbit-auto-evolve tick") \
            and "#refire" in (cc.get("prompt") or "") \
            and cc.get("durable") is False and cc.get("recurring") is False \
            and cc.get("cron"):
        ok("B: croncreate one-shot block carries cron/prompt/durable=false")
    else:
        fail(f"B: croncreate block malformed: {cc!r}")
    # Pinned-minute amendment (#531): cron must be a pinned "M H * * *" form,
    # NOT "*/1 * * * *", with minute field neither 0 nor 30.
    cron = (cc or {}).get("cron", "")
    if cc and cc.get("recurring") is False and cc.get("durable") is False:
        ok("B: croncreate.recurring is False and croncreate.durable is False")
    else:
        fail(f"B: recurring/durable not both False: {cc!r}")
    if cron == "*/1 * * * *":
        fail("B: croncreate.cron is the fragile every-minute '*/1 * * * *'")
    elif PINNED_RE.match(cron):
        minute = int(cron.split()[0])
        if minute not in (0, 30):
            ok(f"B: croncreate.cron is a pinned 'M H * * *' with safe minute {minute}")
        else:
            fail(f"B: pinned cron minute is on a :00/:30 mark: {cron!r}")
    else:
        fail(f"B: croncreate.cron is not a pinned 'M H * * *' expression: {cron!r}")

# C — empty queue
with tempfile.TemporaryDirectory() as d:
    proc = run(d, EMPTY, restricted=False)
    j = parsed(proc)
    if proc.returncode == 0 and j and j.get("decision") == "idle":
        ok("C: empty queue -> idle")
    else:
        fail(f"C: out={proc.stdout!r} err={proc.stderr!r}")

# D — decision logged
with tempfile.TemporaryDirectory() as d:
    run(d, EMPTY, restricted=False)
    log = os.path.join(d, ".rabbit", "tick.log")
    if os.path.isfile(log) and "idle" in open(log).read().lower():
        ok("D: the idle decision was logged to .rabbit/tick.log")
    else:
        fail("D: decision not logged to .rabbit/tick.log")

# E — --help smoke
proc = subprocess.run(
    [sys.executable, DECIDE, "--help"], capture_output=True, text=True,
)
if proc.returncode == 0 and "refire" in (proc.stdout + proc.stderr).lower():
    ok("E: --help exits 0 with recognizable usage")
else:
    fail(f"E: --help exit {proc.returncode}; out={proc.stdout!r}")

# F — _pinned_oneshot_cron(now=...) with injected wall clock (deterministic)
mod = _load_decide_module()
if not hasattr(mod, "_pinned_oneshot_cron"):
    fail("F: schedule-decision.py has no _pinned_oneshot_cron helper")
else:
    pin = mod._pinned_oneshot_cron

    # Inv 33 arm-time-skid buffer (#748): the pinned minute is the current
    # minute + 2 (a 2-minute buffer), NOT +1. The +1 form was dropped ~14% of
    # the time when the dispatcher's CronList->CronDelete->CronCreate dedup
    # round-trip crossed the wall-clock minute boundary, parking the one-shot
    # ~24h out. A 2-minute buffer guarantees the pinned minute is STRICTLY in
    # the future even after a multi-second arm-time round-trip.
    # Ordinary minute: 10:15 -> minute 17 at hour 10 (15 + 2).
    if pin(now=datetime(2026, 6, 3, 10, 15)) == "17 10 * * *":
        ok("F: 10:15 -> '17 10 * * *' (current minute + 2 buffer, #748)")
    else:
        fail(f"F: 10:15 -> {pin(now=datetime(2026, 6, 3, 10, 15))!r}, expected '17 10 * * *'")

    # Nudge off :00 — minute 59 + 2 -> minute 1 next hour (already off :00).
    res = pin(now=datetime(2026, 6, 3, 10, 59))
    parts = res.split()
    if PINNED_RE.match(res) and int(parts[0]) not in (0, 30):
        ok(f"F: 10:59 -> {res!r} avoids :00 (rollover with +2 buffer)")
    else:
        fail(f"F: 10:59 -> {res!r} landed on a :00/:30 mark")

    # Nudge off :30 — minute 28 + 2 -> minute 30 -> nudged to 31.
    res = pin(now=datetime(2026, 6, 3, 14, 28))
    parts = res.split()
    if PINNED_RE.match(res) and int(parts[0]) not in (0, 30):
        ok(f"F: 14:28 -> {res!r} avoids :30")
    else:
        fail(f"F: 14:28 -> {res!r} landed on a :00/:30 mark")

    # The default (now=None) must still be a valid pinned, safe expression.
    res = pin()
    if PINNED_RE.match(res) and res != "*/1 * * * *" \
            and int(res.split()[0]) not in (0, 30):
        ok(f"F: default now -> pinned safe cron {res!r}")
    else:
        fail(f"F: default now -> unsafe/non-pinned cron {res!r}")

# --- Inv 33: at-most-one refire dedup with a labelled signature (#559) -------

REFIRE_MARKER = "#refire"


# G — the emitted refire one-shot carries the refire marker so it is
# distinguishable from the recurring heartbeat (which fires the bare prompt).
with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=True)
    j = parsed(proc) or {}
    cc = j.get("croncreate") or {}
    create = (j.get("dispatcher_actions") or {}).get("create_refire") or {}
    # The refire prompt MUST carry the marker; the heartbeat prompt
    # (install-cron HEARTBEAT_PROMPT) is the bare "/rabbit-auto-evolve tick".
    if REFIRE_MARKER in (cc.get("prompt") or "") \
            and REFIRE_MARKER in (create.get("prompt") or ""):
        ok("G: refire one-shot prompt carries the #refire marker (croncreate "
           "+ create_refire)")
    else:
        fail(f"G: refire prompt missing #refire marker: croncreate={cc!r} "
             f"create_refire={create!r}")
    if create.get("recurring") is False and create.get("durable") is False:
        ok("G: create_refire is non-recurring and non-durable")
    else:
        fail(f"G: create_refire not both False: {create!r}")


# H — dedup decision from an injected CronList snapshot holding a PRIOR refire
# one-shot + the recurring heartbeat. The prior refire must be selected for
# deletion; the heartbeat must be PRESERVED and never selected for deletion;
# exactly one refire is created.
HEARTBEAT_ENTRY = {
    "id": "cron-heartbeat-1",
    "prompt": "/rabbit-auto-evolve tick",
    "cron": "13,43 * * * *",
    "recurring": True,
    "durable": True,
}
PRIOR_REFIRE_ENTRY = {
    "id": "cron-refire-7",
    "prompt": "/rabbit-auto-evolve tick #refire",
    "cron": "16 10 * * *",
    "recurring": False,
    "durable": False,
}
SNAPSHOT = json.dumps([HEARTBEAT_ENTRY, PRIOR_REFIRE_ENTRY])

with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=True, cron_list=SNAPSHOT)
    j = parsed(proc) or {}
    da = j.get("dispatcher_actions") or {}
    delete_ids = da.get("delete_refire_ids")
    preserve_ids = da.get("preserve_heartbeat_ids")
    create = da.get("create_refire")
    if isinstance(delete_ids, list) and "cron-refire-7" in delete_ids:
        ok("H: prior refire id is in delete_refire_ids")
    else:
        fail(f"H: prior refire id NOT scheduled for deletion: {da!r}")
    # The heartbeat must NEVER be selected for deletion.
    if isinstance(delete_ids, list) and "cron-heartbeat-1" not in delete_ids:
        ok("H: heartbeat id is NOT in delete_refire_ids")
    else:
        fail(f"H: heartbeat id wrongly scheduled for deletion: {da!r}")
    if isinstance(preserve_ids, list) and "cron-heartbeat-1" in preserve_ids:
        ok("H: heartbeat id is in preserve_heartbeat_ids")
    else:
        fail(f"H: heartbeat id not preserved: {da!r}")
    # Exactly one refire is created, and it carries the marker.
    if isinstance(create, dict) and REFIRE_MARKER in (create.get("prompt") or ""):
        ok("H: exactly one create_refire emitted with the #refire marker")
    else:
        fail(f"H: create_refire malformed/absent: {da!r}")


# H2 — absent CronList snapshot is treated as empty: no deletions, still one
# create_refire.
with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=True)  # no cron_list
    j = parsed(proc) or {}
    da = j.get("dispatcher_actions") or {}
    if da.get("delete_refire_ids") == [] and isinstance(da.get("create_refire"), dict):
        ok("H2: absent CronList -> empty delete list + one create_refire")
    else:
        fail(f"H2: absent CronList not handled as empty: {da!r}")


# I — is_refire_oneshot(entry) pure predicate unit tests.
mod = _load_decide_module()
if not hasattr(mod, "is_refire_oneshot"):
    fail("I: schedule-decision.py has no is_refire_oneshot predicate")
else:
    is_refire = mod.is_refire_oneshot
    # A marked, non-recurring, non-durable one-shot IS a refire.
    if is_refire(PRIOR_REFIRE_ENTRY) is True:
        ok("I: marked non-recurring non-durable entry -> refire (True)")
    else:
        fail("I: marked refire one-shot not recognised as a refire")
    # The recurring/durable heartbeat (no marker) is NEVER a refire.
    if is_refire(HEARTBEAT_ENTRY) is False:
        ok("I: recurring/durable heartbeat -> NOT a refire (False)")
    else:
        fail("I: heartbeat wrongly classified as a refire (would be deleted!)")
    # A recurring entry that happens to carry the marker is still NOT a refire
    # one-shot (a refire is a ONE-SHOT; recurring excludes it from the dedup
    # target so we never tear down a recurring schedule).
    marked_recurring = dict(HEARTBEAT_ENTRY)
    marked_recurring["prompt"] = "/rabbit-auto-evolve tick #refire"
    marked_recurring["recurring"] = True
    if is_refire(marked_recurring) is False:
        ok("I: marker on a RECURRING entry -> NOT a refire one-shot (False)")
    else:
        fail("I: a recurring marked entry wrongly classified as a refire")
    # A bare one-shot with no marker is NOT a refire (can't prove it's ours).
    bare_oneshot = dict(PRIOR_REFIRE_ENTRY)
    bare_oneshot["prompt"] = "/rabbit-auto-evolve tick"
    if is_refire(bare_oneshot) is False:
        ok("I: unmarked one-shot -> NOT a refire (False)")
    else:
        fail("I: an unmarked one-shot wrongly classified as a refire")

# --- J: arm-time minute-boundary skid robustness (Inv 33, #748) --------------
# The bug: the pinned minute was computed at DECISION time as current+1, but the
# dispatcher's CronList->CronDelete->CronCreate dedup round-trip eats several
# seconds. When the decision lands in the final seconds of a minute, that
# round-trip crosses the minute boundary, so a +1 pinned minute became the
# CURRENT (already-started) minute -> the one-shot is parked ~24h out (dropped
# ~14% of the time). The fix pins the minute with a >=2-minute buffer so the
# pinned minute is STRICTLY in the future even after the multi-second round-trip.
mod = _load_decide_module()
pin = mod._pinned_oneshot_cron
MINUTE_BUFFER = 2  # the required buffer in minutes (#748)

# Simulate decision-time clocks near a minute boundary across every minute of
# the hour (including the dangerous :59.9 final-seconds case): the pinned minute
# must be at least MINUTE_BUFFER minutes ahead of the decision minute, so the
# dedup round-trip (a few seconds, never >= 2 min) cannot cross it.
skid_ok = True
for minute in range(60):
    # Decision lands in the final seconds of the minute (the worst case).
    now = datetime(2026, 6, 3, 10, minute, 59)
    cron = pin(now=now)
    if not PINNED_RE.match(cron):
        fail(f"J: pin near :{minute:02d}:59 is not a pinned 'M H * * *': {cron!r}")
        skid_ok = False
        break
    pinned_min = int(cron.split()[0])
    pinned_hr = int(cron.split()[1])
    # Compute the wall-clock gap (minutes) from the decision minute to the
    # pinned minute, accounting for the hour rollover.
    decision_abs = now.hour * 60 + now.minute
    pinned_abs = pinned_hr * 60 + pinned_min
    if pinned_abs <= decision_abs:  # rolled past the hour (or day) boundary
        pinned_abs += 24 * 60
    gap = pinned_abs - decision_abs
    if gap < MINUTE_BUFFER:
        fail(f"J: decision at 10:{minute:02d}:59 -> pinned {cron!r} is only "
             f"{gap} min ahead (< {MINUTE_BUFFER}); arm-time skid can drop it")
        skid_ok = False
        break
    if pinned_min in (0, 30):
        fail(f"J: decision at 10:{minute:02d}:59 -> pinned minute on :00/:30: {cron!r}")
        skid_ok = False
        break
if skid_ok:
    ok(f"J: pinned minute is >= {MINUTE_BUFFER} min ahead for every "
       "near-boundary decision minute (arm-time skid closed, #748)")

# J2 — end-to-end: the emitted croncreate one-shot (restricted/croncreate path)
# is a valid pinned 'M H * * *' AND preserves the #refire marker + the
# durable/recurring=false flags, with the buffered minute.
with tempfile.TemporaryDirectory() as d:
    proc = run(d, NONEMPTY, restricted=True)
    j = parsed(proc) or {}
    cc = j.get("croncreate") or {}
    cron = cc.get("cron") or ""
    create = (j.get("dispatcher_actions") or {}).get("create_refire") or {}
    if PINNED_RE.match(cron) and cron != "*/1 * * * *" \
            and int(cron.split()[0]) not in (0, 30):
        ok(f"J2: emitted croncreate.cron is a valid pinned 'M H * * *': {cron!r}")
    else:
        fail(f"J2: emitted croncreate.cron not a safe pinned form: {cron!r}")
    if REFIRE_MARKER in (cc.get("prompt") or "") \
            and cc.get("recurring") is False and cc.get("durable") is False \
            and REFIRE_MARKER in (create.get("prompt") or "") \
            and create.get("recurring") is False and create.get("durable") is False:
        ok("J2: #refire marker + durable/recurring=false preserved after buffer fix")
    else:
        fail(f"J2: marker/flags not preserved: croncreate={cc!r} create={create!r}")

sys.exit(FAIL)
