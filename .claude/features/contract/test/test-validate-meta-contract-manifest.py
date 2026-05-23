#!/usr/bin/env python3
"""test-validate-meta-contract-manifest.py — exercises the manifest-section
arm of validate_meta_contract. Uses inline fixture feature.json files in a
temp dir so no live features are touched.
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from lib.checks import validate_meta_contract  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def write_feature(tmpdir, data):
    path = os.path.join(tmpdir, "feature.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return tmpdir


with tempfile.TemporaryDirectory() as td:
    # t1: feature.json with no manifest section -> pass (optional)
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x"})
    r = validate_meta_contract(td)
    if r.passed:
        ok("t1: absent manifest section is accepted")
    else:
        fail(f"t1: absent manifest rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t2: valid empty manifest -> pass
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x", "manifest": []})
    r = validate_meta_contract(td)
    if r.passed:
        ok("t2: empty manifest array is accepted")
    else:
        fail(f"t2: empty manifest rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t3: valid populated manifest -> pass
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": [
                           {"api": "publish_skill", "args": {"source": "skills/x/SKILL.md"}},
                           {"api": "publish_hook", "args": {"event": "Stop", "source": "hooks/x.py"}}
                       ]})
    r = validate_meta_contract(td)
    if r.passed:
        ok("t3: populated valid manifest is accepted")
    else:
        fail(f"t3: valid manifest rejected: {r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t4: manifest is not an array -> fail with descriptive error
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": {"api": "x"}})
    r = validate_meta_contract(td)
    if not r.passed and any("must be an array" in m for m in r.messages):
        ok("t4: non-array manifest is rejected with descriptive message")
    else:
        fail(f"t4: non-array manifest acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t5: manifest item missing 'api' -> fail
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": [{"args": {}}]})
    r = validate_meta_contract(td)
    if not r.passed and any("missing required 'api'" in m for m in r.messages):
        ok("t5: manifest item missing 'api' is rejected")
    else:
        fail(f"t5: missing-api acceptance bug: passed={r.passed}, messages={r.messages}")

with tempfile.TemporaryDirectory() as td:
    # t6: manifest item with unknown api -> fail
    write_feature(td, {"name": "x", "version": "1.0.0", "owner": "x", "tdd_state": "spec", "summary": "x", "surface": {}, "deprecation_criterion": "x",
                       "manifest": [{"api": "publish_bogus", "args": {}}]})
    r = validate_meta_contract(td)
    if not r.passed and any("unknown publish api" in m for m in r.messages):
        ok("t6: unknown api is rejected")
    else:
        fail(f"t6: unknown-api acceptance bug: passed={r.passed}, messages={r.messages}")

if FAIL:
    print("test-validate-meta-contract-manifest: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-validate-meta-contract-manifest: all checks passed.")
