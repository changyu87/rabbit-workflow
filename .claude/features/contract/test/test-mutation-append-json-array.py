#!/usr/bin/env python3
"""test-mutation-append-json-array.py — exercises append_json_array:
append a value to a JSON array at a dotted path. Creates the array (and
file) if absent. Idempotent on duplicate values (does not re-append).
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import append_json_array, set_json_key  # noqa: E402

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


# t1: append to absent file creates file + array
with tempfile.TemporaryDirectory() as root:
    r = append_json_array(".s.json", "permissions.allow", "Bash(ls:*)", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json") != {"permissions": {"allow": ["Bash(ls:*)"]}}:
        fail(f"t1: wrong content: {load(root, '.s.json')}")
    else:
        ok("t1: append to absent file creates array")

# t2: append to existing array
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.allow", ["A"], repo_root=root)
    r = append_json_array(".s.json", "permissions.allow", "B", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    elif load(root, ".s.json")["permissions"]["allow"] != ["A", "B"]:
        fail(f"t2: wrong array: {load(root, '.s.json')}")
    else:
        ok("t2: append to existing array")

# t3: idempotent — duplicate value is no-op (does not re-append)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.allow", ["A"], repo_root=root)
    r = append_json_array(".s.json", "permissions.allow", "A", repo_root=root)
    if not r.passed:
        fail(f"t3: failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: duplicate should be no-op: {r.messages}")
    elif load(root, ".s.json")["permissions"]["allow"] != ["A"]:
        fail(f"t3: array changed: {load(root, '.s.json')}")
    else:
        ok("t3: idempotent — duplicate value is no-op")

# t4: existing non-array value at key → error (do not coerce)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x", "not-an-array", repo_root=root)
    r = append_json_array(".s.json", "x", "B", repo_root=root)
    if r.passed:
        fail("t4: non-array key should be rejected (would lose data)")
    elif not any("array" in m.lower() for m in r.messages):
        fail(f"t4: error should mention array: {r.messages}")
    else:
        ok("t4: existing non-array value rejected (data preserved)")

# t5: preserves sibling top-level keys
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "keep", "this", repo_root=root)
    set_json_key(".s.json", "permissions.allow", ["A"], repo_root=root)
    r = append_json_array(".s.json", "permissions.allow", "B", repo_root=root)
    d = load(root, ".s.json")
    if not r.passed:
        fail(f"t5: failed: {r.messages}")
    elif d.get("keep") != "this":
        fail(f"t5: sibling key lost: {d}")
    elif d["permissions"]["allow"] != ["A", "B"]:
        fail(f"t5: wrong array: {d}")
    else:
        ok("t5: preserves sibling keys")

if FAIL:
    print("test-mutation-append-json-array: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-append-json-array: all checks passed.")
