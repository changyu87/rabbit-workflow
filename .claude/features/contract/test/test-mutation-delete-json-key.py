#!/usr/bin/env python3
"""test-mutation-delete-json-key.py — exercises delete_json_key: remove a
key at a dotted JSON path. Idempotent (no-op if key absent). Does not
remove the empty-parent object (preserves sibling keys at every level).
"""

import os
import sys
import json
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import delete_json_key, set_json_key  # noqa: E402

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


# t1: delete existing top-level key
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "x", 1, repo_root=root)
    r = delete_json_key(".s.json", "x", repo_root=root)
    if not r.passed:
        fail(f"t1: failed: {r.messages}")
    elif load(root, ".s.json") != {}:
        fail(f"t1: wrong content: {load(root, '.s.json')}")
    else:
        ok("t1: deletes existing top-level key")

# t2: delete dotted key, preserve siblings + parent
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "permissions.defaultMode", "bypassPermissions", repo_root=root)
    set_json_key(".s.json", "permissions.allow", ["X"], repo_root=root)
    r = delete_json_key(".s.json", "permissions.defaultMode", repo_root=root)
    if not r.passed:
        fail(f"t2: failed: {r.messages}")
    else:
        d = load(root, ".s.json")
        if "permissions" not in d:
            fail(f"t2: parent object removed: {d}")
        elif "defaultMode" in d["permissions"]:
            fail(f"t2: key not deleted: {d}")
        elif d["permissions"].get("allow") != ["X"]:
            fail(f"t2: sibling key lost: {d}")
        else:
            ok("t2: deletes dotted key, preserves siblings and parent object")

# t3: idempotent — delete absent key
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "other", 1, repo_root=root)
    r = delete_json_key(".s.json", "never.existed", repo_root=root)
    if not r.passed:
        fail(f"t3: absent-key delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: absent-key delete should be no-op: {r.messages}")
    else:
        ok("t3: idempotent — absent key delete is no-op")

# t4: missing intermediate dict → no-op (not error)
with tempfile.TemporaryDirectory() as root:
    set_json_key(".s.json", "a", 1, repo_root=root)
    r = delete_json_key(".s.json", "a.b.c", repo_root=root)
    if not r.passed:
        fail(f"t4: missing-intermediate failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t4: should report no-op: {r.messages}")
    elif load(root, ".s.json") != {"a": 1}:
        fail(f"t4: original data disturbed: {load(root, '.s.json')}")
    else:
        ok("t4: missing intermediate is no-op (data preserved)")

# t5: absent file is no-op (not error)
with tempfile.TemporaryDirectory() as root:
    r = delete_json_key(".s.json", "x", repo_root=root)
    if not r.passed:
        fail(f"t5: absent-file delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t5: absent-file delete should be no-op: {r.messages}")
    else:
        ok("t5: absent file is no-op")

# t6: malformed JSON → fail, no overwrite
with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, ".s.json")
    with open(path, "w") as f:
        f.write("{ not json")
    r = delete_json_key(".s.json", "a", repo_root=root)
    if r.passed:
        fail("t6: malformed JSON should be rejected")
    elif open(path).read() != "{ not json":
        fail("t6: file altered despite failure")
    else:
        ok("t6: malformed JSON rejected; file preserved")

if FAIL:
    print("test-mutation-delete-json-key: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-delete-json-key: all checks passed.")
