#!/usr/bin/env python3
"""test-mutation-set-json-key.py — exercises set_json_key: write a value at
a dotted JSON-key path (e.g. 'permissions.defaultMode') in a JSON file.
Creates the file if absent. Creates intermediate objects as needed.
Idempotent on identical value.
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import set_json_key  # noqa: E402

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


# t1: set top-level key in fresh file
with tempfile.TemporaryDirectory() as root:
    r = set_json_key(".s.json", "model", "claude-opus-4-7", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json") != {"model": "claude-opus-4-7"}:
        fail(f"t1: wrong content: {load(root, '.s.json')}")
    else:
        ok("t1: set top-level key in fresh file")

# t2: set dotted key (creates intermediate dict)
with tempfile.TemporaryDirectory() as root:
    r = set_json_key(".s.json", "permissions.defaultMode", "bypassPermissions", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    elif load(root, ".s.json") != {"permissions": {"defaultMode": "bypassPermissions"}}:
        fail(f"t2: wrong content: {load(root, '.s.json')}")
    else:
        ok("t2: dotted key creates intermediate dict")

# t3: idempotent — same value returns no-op
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "a.b", 1, repo_root=root)
    r = set_json_key(".s.json", "a.b", 1, repo_root=root)
    if not r.passed:
        fail(f"t3: second call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: should report no-op: {r.messages}")
    else:
        ok("t3: idempotent — same value is no-op")

# t4: changed value overwrites
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "a.b", 1, repo_root=root)
    r = set_json_key(".s.json", "a.b", 2, repo_root=root)
    if not r.passed:
        fail(f"t4: overwrite failed: {r.messages}")
    elif load(root, ".s.json") != {"a": {"b": 2}}:
        fail(f"t4: wrong content: {load(root, '.s.json')}")
    else:
        ok("t4: changed value overwrites")

# t5: preserves sibling keys at every level
with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, ".s.json")
    with open(path, "w") as f:
        json.dump({"keep": "this", "permissions": {"allow": ["X"]}}, f)
    r = set_json_key(".s.json", "permissions.defaultMode", "bypassPermissions", repo_root=root)
    if not r.passed:
        fail(f"t5: failed: {r.messages}")
    else:
        d = load(root, ".s.json")
        if d.get("keep") != "this":
            fail(f"t5: lost sibling top-level key: {d}")
        elif d.get("permissions", {}).get("allow") != ["X"]:
            fail(f"t5: lost sibling nested key: {d}")
        elif d.get("permissions", {}).get("defaultMode") != "bypassPermissions":
            fail(f"t5: did not set new key: {d}")
        else:
            ok("t5: sibling keys (top-level and nested) preserved")

# t6: non-string value types (int, bool, list) round-trip correctly
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x.n", 42, repo_root=root)
    set_json_key(".s.json", "x.b", True, repo_root=root)
    set_json_key(".s.json", "x.l", [1, 2], repo_root=root)
    d = load(root, ".s.json")
    if d != {"x": {"n": 42, "b": True, "l": [1, 2]}}:
        fail(f"t6: non-string values broken: {d}")
    else:
        ok("t6: int, bool, list values round-trip")

# t7: malformed JSON file → fail, does NOT silently overwrite user data
with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, ".s.json")
    with open(path, "w") as f:
        f.write("not json at all {")
    r = set_json_key(".s.json", "a", 1, repo_root=root)
    if r.passed:
        fail("t7: malformed JSON should be rejected, not silently overwritten")
    elif not any("json" in m.lower() for m in r.messages):
        fail(f"t7: error message should mention JSON: {r.messages}")
    elif open(path).read() != "not json at all {":
        fail("t7: file contents changed despite failure")
    else:
        ok("t7: malformed JSON rejected; file contents preserved")

if FAIL:
    print("test-mutation-set-json-key: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-set-json-key: all checks passed.")
