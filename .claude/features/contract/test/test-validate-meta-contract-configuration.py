#!/usr/bin/env python3
"""test-validate-meta-contract-configuration.py — exercises the
configuration-section arm of validate_meta_contract.
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from lib.checks import validate_meta_contract  # noqa: E402

BASE = {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x"}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write(tmpdir, cfg):
    data = dict(BASE)
    data["configuration"] = cfg
    with open(os.path.join(tmpdir, "feature.json"), "w") as f:
        json.dump(data, f)
    return tmpdir


VALID_VALUES_ENTRY = {
    "id": "x", "subcommand": "x",
    "storage": {"type": "marker-file", "path": ".x"},
    "values": {
        "true":  {"api": "delete_marker", "args": {"path": ".x"}},
        "false": {"api": "write_marker",  "args": {"path": ".x", "content": "y"}}
    },
    "default": "true"
}

VALID_ACTIONS_ENTRY = {
    "id": "x", "subcommand": "x",
    "actions": {
        "lock":   {"api": "run_feature_script", "args": {"script": "scripts/x.py"}},
        "unlock": {"api": "run_feature_script", "args": {"script": "scripts/x.py"}}
    }
}


with tempfile.TemporaryDirectory() as td:
    # t1: empty configuration array -> pass
    r = validate_meta_contract(write(td, []))
    if r.passed:
        ok("t1: empty configuration array is accepted")
    else:
        fail(f"t1: empty configuration rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t2: valid values-style entry -> pass
    r = validate_meta_contract(write(td, [VALID_VALUES_ENTRY]))
    if r.passed:
        ok("t2: valid values-style entry is accepted")
    else:
        fail(f"t2: valid values rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t3: valid actions-style entry -> pass
    r = validate_meta_contract(write(td, [VALID_ACTIONS_ENTRY]))
    if r.passed:
        ok("t3: valid actions-style entry is accepted")
    else:
        fail(f"t3: valid actions rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t4: configuration not an array -> fail
    r = validate_meta_contract(write(td, {"id": "x"}))
    if not r.passed and any("must be an array" in m for m in r.messages):
        ok("t4: non-array configuration is rejected")
    else:
        fail(f"t4: non-array acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t5: entry missing id -> fail
    bad = dict(VALID_VALUES_ENTRY); del bad["id"]
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("missing required 'id'" in m for m in r.messages):
        ok("t5: entry missing 'id' is rejected")
    else:
        fail(f"t5: missing-id acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t6: entry with both values AND actions -> fail (oneOf)
    bad = dict(VALID_VALUES_ENTRY)
    bad["actions"] = VALID_ACTIONS_ENTRY["actions"]
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("exactly one of 'values' or 'actions'" in m for m in r.messages):
        ok("t6: both values and actions is rejected (oneOf)")
    else:
        fail(f"t6: both-values-and-actions acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t7: entry with neither values nor actions -> fail (oneOf)
    bad = {"id": "x", "subcommand": "x"}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("exactly one of 'values' or 'actions'" in m for m in r.messages):
        ok("t7: neither values nor actions is rejected (oneOf)")
    else:
        fail(f"t7: neither-values-nor-actions acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t8: unknown mutation api -> fail
    bad = dict(VALID_VALUES_ENTRY)
    bad["values"] = {"true": {"api": "mutate_bogus", "args": {}}}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("unknown mutation api" in m for m in r.messages):
        ok("t8: unknown mutation api is rejected")
    else:
        fail(f"t8: unknown-mutation-api acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t9: unknown storage type -> fail
    bad = dict(VALID_VALUES_ENTRY)
    bad["storage"] = {"type": "magic"}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("unknown storage type" in m for m in r.messages):
        ok("t9: unknown storage type is rejected")
    else:
        fail(f"t9: unknown-storage-type acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t10: storage object missing 'type' key -> "missing required 'type'" (not "unknown storage type None")
    bad = dict(VALID_VALUES_ENTRY)
    bad["storage"] = {}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("missing required 'type'" in m for m in r.messages):
        ok("t10: storage missing 'type' is reported as missing-key (not as unknown-type 'None')")
    else:
        fail(f"t10: missing-storage-type acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t11: alert-message missing 'color' must NOT double-report (one missing-key error, no enum-mismatch error)
    bad = dict(VALID_VALUES_ENTRY)
    bad["alert-on"] = "false"
    bad["alert-message"] = {"text": "x", "icon": "x"}
    r = validate_meta_contract(write(td, [bad]))
    missing_msgs = [m for m in r.messages if "missing required 'color'" in m]
    enum_msgs = [m for m in r.messages if "color must be one of" in m]
    if not r.passed and len(missing_msgs) == 1 and len(enum_msgs) == 0:
        ok("t11: missing alert-message.color emits exactly one missing-key error (no double-report)")
    else:
        fail(f"t11: alert-message.color double-report bug: passed={r.passed}, missing={missing_msgs}, enum={enum_msgs}")

with tempfile.TemporaryDirectory() as td:
    # t12: default that is not a key in values -> fail (unreachable default)
    bad = dict(VALID_VALUES_ENTRY)
    bad["default"] = "maybe"
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("default 'maybe' is not a key in values" in m for m in r.messages):
        ok("t12: default that is not a values key is rejected")
    else:
        fail(f"t12: unreachable-default acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t13: alert-on that is not a key in values -> fail
    bad = dict(VALID_VALUES_ENTRY)
    bad["alert-on"] = "maybe"
    bad["alert-message"] = {"text": "x", "icon": "x", "color": "red"}
    r = validate_meta_contract(write(td, [bad]))
    if not r.passed and any("alert-on 'maybe' is not a key in values" in m for m in r.messages):
        ok("t13: alert-on that is not a values key is rejected")
    else:
        fail(f"t13: unreachable-alert-on acceptance bug: passed={r.passed}, messages={r.messages}")

if FAIL:
    print("test-validate-meta-contract-configuration: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-configuration: all checks passed.")
