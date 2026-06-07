#!/usr/bin/env python3
"""Inv 53 — `abort` rolls back tdd_state via optional `_pre_touch_state`
field; defaults to `test-red` when the field is absent. The
`_pre_touch_state` field is removed from feature.json after the rollback
(consumed by the abort).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TDD_STEP = os.path.join(FEATURE_DIR, "scripts", "tdd-step.py")

sys.path.insert(0, SCRIPT_DIR)
from state_machine_helpers import make_feature_dir  # noqa: E402

TMPROOT = tempfile.mkdtemp()

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def run(*args):
    return subprocess.run(
        ["python3", TDD_STEP] + list(args),
        capture_output=True, text=True,
    )


def _read_feature(d):
    with open(os.path.join(d, "feature.json")) as f:
        return json.load(f)


def _write_feature(d, data):
    with open(os.path.join(d, "feature.json"), "w") as f:
        json.dump(data, f, indent=2)


# Inv 53 (a): _pre_touch_state present => rollback to that value, field removed.
def t_pre_touch_state_consumed():
    d = os.path.join(TMPROOT, "pre_touch")
    make_feature_dir(d, "pre_touch", "sync-deployed")
    data = _read_feature(d)
    data["_pre_touch_state"] = "impl"
    _write_feature(d, data)
    res = run("abort", d, "--reason", "discovered-blocker")
    if res.returncode != 0:
        ko(f"rollback w/pre_touch: rc={res.returncode} stderr={res.stderr!r}")
        return
    data = _read_feature(d)
    if data.get("tdd_state") == "impl":
        ok("Inv 53: rollback uses _pre_touch_state value ('impl')")
    else:
        ko(f"Inv 53: tdd_state={data.get('tdd_state')!r}, expected 'impl'")
    if "_pre_touch_state" not in data:
        ok("Inv 53: _pre_touch_state field removed after abort (consumed)")
    else:
        ko("Inv 53: _pre_touch_state still present after abort")


# Inv 53 (b): no _pre_touch_state => rollback to test-red default.
def t_default_test_red():
    d = os.path.join(TMPROOT, "default_red")
    make_feature_dir(d, "default_red", "sync-deployed")
    # Ensure field absent.
    data = _read_feature(d)
    data.pop("_pre_touch_state", None)
    _write_feature(d, data)
    res = run("abort", d, "--reason", "blocked-by-#329")
    if res.returncode != 0:
        ko(f"rollback default: rc={res.returncode} stderr={res.stderr!r}")
        return
    data = _read_feature(d)
    if data.get("tdd_state") == "test-red":
        ok("Inv 53: rollback defaults to test-red when _pre_touch_state absent")
    else:
        ko(f"Inv 53: tdd_state={data.get('tdd_state')!r}, expected 'test-red'")
    if "_pre_touch_state" not in data:
        ok("Inv 53: _pre_touch_state still absent after default rollback")
    else:
        ko("Inv 53: _pre_touch_state unexpectedly added after default rollback")


# Inv 53 (c): round-trip cleanliness — abort from impl with
# _pre_touch_state='test-red', verify final feature.json is clean.
def t_round_trip_clean():
    d = os.path.join(TMPROOT, "round_trip")
    make_feature_dir(d, "round_trip", "impl")
    data = _read_feature(d)
    data["_pre_touch_state"] = "test-red"
    _write_feature(d, data)
    res = run("abort", d, "--reason", "external-dep-missing")
    if res.returncode != 0:
        ko(f"round_trip: rc={res.returncode} stderr={res.stderr!r}")
        return
    data = _read_feature(d)
    # Confirm the JSON is still readable, no leftover field, tdd_state correct.
    if (data.get("tdd_state") == "test-red"
            and "_pre_touch_state" not in data
            and data.get("name") == "round_trip"):
        ok("Inv 53: post-abort feature.json is clean (no leftover _pre_touch_state)")
    else:
        ko(f"Inv 53: post-abort feature.json shape unexpected: {data!r}")


t_pre_touch_state_consumed()
t_default_test_red()
t_round_trip_clean()

print()
print(f"summary: {PASS} passed, {FAIL} failed")
shutil.rmtree(TMPROOT, ignore_errors=True)
sys.exit(0 if FAIL == 0 else 1)
