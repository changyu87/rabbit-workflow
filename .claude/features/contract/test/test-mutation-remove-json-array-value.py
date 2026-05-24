#!/usr/bin/env python3
"""test-mutation-remove-json-array-value.py — exercises
remove_json_array_value: remove a single value from a JSON array at a
dotted path. Idempotent (no-op on absent file/key/value). Empty array
remains as []; key is not auto-removed.
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import remove_json_array_value, set_json_key  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def load(root, name):
    with open(os.path.join(root, name)) as f:
        return json.load(f)


# t1: remove existing value from array
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.allow", ["A", "B", "C"], repo_root=root)
    r = remove_json_array_value(".s.json", "permissions.allow", "B", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json")["permissions"]["allow"] != ["A", "C"]:
        fail(f"t1: wrong array: {load(root, '.s.json')}")
    else:
        ok("t1: removes existing value")

# t2: idempotent — absent value is no-op
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "p", ["A"], repo_root=root)
    r = remove_json_array_value(".s.json", "p", "Z", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: should be no-op: {r.messages}")
    elif load(root, ".s.json")["p"] != ["A"]:
        fail(f"t2: array changed: {load(root, '.s.json')}")
    else:
        ok("t2: idempotent — absent value is no-op")

# t3: absent file is no-op (not error)
with tempfile.TemporaryDirectory() as root:
    r = remove_json_array_value(".s.json", "p", "X", repo_root=root)
    if not r.passed:
        fail(f"t3: absent-file failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: absent file should be no-op: {r.messages}")
    else:
        ok("t3: absent file is no-op")

# t4: absent key is no-op
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "other", 1, repo_root=root)
    r = remove_json_array_value(".s.json", "never.existed", "X", repo_root=root)
    if not r.passed:
        fail(f"t4: absent-key failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t4: absent key should be no-op: {r.messages}")
    else:
        ok("t4: absent key is no-op")

# t5: removing only value leaves empty array (key NOT auto-removed)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "p", ["A"], repo_root=root)
    r = remove_json_array_value(".s.json", "p", "A", repo_root=root)
    if not r.passed:
        fail(f"t5: failed: {r.messages}")
    elif load(root, ".s.json") != {"p": []}:
        fail(f"t5: empty array not preserved: {load(root, '.s.json')}")
    else:
        ok("t5: empty array remains; key not auto-removed")

# t6: duplicate values — removes only first occurrence (deterministic)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "p", ["A", "B", "A"], repo_root=root)
    r = remove_json_array_value(".s.json", "p", "A", repo_root=root)
    if not r.passed:
        fail(f"t6: failed: {r.messages}")
    elif load(root, ".s.json")["p"] != ["B", "A"]:
        fail(f"t6: wrong array (expected single-occurrence removal): {load(root, '.s.json')}")
    else:
        ok("t6: removes first occurrence only (single-removal semantics)")

# t7: existing non-array value at key → error
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x", "string-not-array", repo_root=root)
    r = remove_json_array_value(".s.json", "x", "Z", repo_root=root)
    if r.passed:
        fail("t7: non-array key should be rejected")
    elif not any("array" in m.lower() for m in r.messages):
        fail(f"t7: error should mention array: {r.messages}")
    else:
        ok("t7: non-array value rejected (data preserved)")

if FAIL:
    print("test-mutation-remove-json-array-value: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-remove-json-array-value: all checks passed.")
