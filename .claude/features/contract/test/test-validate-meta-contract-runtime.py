#!/usr/bin/env python3
"""test-validate-meta-contract-runtime.py — exercises the runtime-section
arm of validate_meta_contract.
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


def write(tmpdir, runtime):
    data = dict(BASE)
    data["runtime"] = runtime
    with open(os.path.join(tmpdir, "feature.json"), "w") as f:
        json.dump(data, f)
    return tmpdir


with tempfile.TemporaryDirectory() as td:
    # t1: empty runtime object -> pass
    r = validate_meta_contract(write(td, {}))
    if r.passed:
        ok("t1: empty runtime object is accepted")
    else:
        fail(f"t1: empty runtime rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t2: valid runtime with one Stop call -> pass
    r = validate_meta_contract(write(td, {
        "Stop": [{"api": "check_marker_alert", "args": {"path": ".x", "alert": {"text": "x", "icon": "x", "color": "red"}}}]
    }))
    if r.passed:
        ok("t2: valid Stop runtime is accepted")
    else:
        fail(f"t2: valid runtime rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t3: runtime not an object -> fail
    r = validate_meta_contract(write(td, ["bad"]))
    if not r.passed and any("must be an object" in m for m in r.messages):
        ok("t3: non-object runtime is rejected")
    else:
        fail(f"t3: non-object runtime acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t4: unknown event key -> fail
    r = validate_meta_contract(write(td, {"Foo": []}))
    if not r.passed and any("unknown event" in m for m in r.messages):
        ok("t4: unknown event key is rejected")
    else:
        fail(f"t4: unknown event acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t5: event value not an array -> fail
    r = validate_meta_contract(write(td, {"Stop": {"api": "x"}}))
    if not r.passed and any("must be an array" in m for m in r.messages):
        ok("t5: non-array event value is rejected")
    else:
        fail(f"t5: non-array event acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t6: unknown runtime api -> fail
    r = validate_meta_contract(write(td, {"Stop": [{"api": "check_bogus", "args": {}}]}))
    if not r.passed and any("unknown runtime api" in m for m in r.messages):
        ok("t6: unknown runtime api is rejected")
    else:
        fail(f"t6: unknown runtime api acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t7: runtime item missing 'api' alone -> message must say 'api' specifically (post-fix 62995191)
    r = validate_meta_contract(write(td, {"Stop": [{"args": {}}]}))
    if not r.passed and any("missing required 'api' field" in m for m in r.messages):
        ok("t7: runtime item missing 'api' is rejected with field-specific message")
    else:
        fail(f"t7: missing-api acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t8: runtime item missing 'args' alone -> message must say 'args' specifically (post-fix 62995191)
    r = validate_meta_contract(write(td, {"Stop": [{"api": "check_marker_alert"}]}))
    if not r.passed and any("missing required 'args' field" in m for m in r.messages):
        ok("t8: runtime item missing 'args' is rejected with field-specific message")
    else:
        fail(f"t8: missing-args acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t9: runtime item with extra keys beyond {api, args} -> fail
    r = validate_meta_contract(write(td, {"Stop": [{"api": "check_marker_alert", "args": {}, "stray": 1}]}))
    if not r.passed and any("unexpected keys" in m and "stray" in m for m in r.messages):
        ok("t9: runtime item with extra keys is rejected")
    else:
        fail(f"t9: extra-keys acceptance bug: passed={r.passed}, messages={r.messages}")

if FAIL:
    print("test-validate-meta-contract-runtime: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-runtime: all checks passed.")
