#!/usr/bin/env python3
"""test-publish-settings.py — exercises publish_settings: idempotent copy of a
feature's settings.json source to .claude/settings.json.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_settings  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


SAMPLE = {
    "env": {"RABBIT_REFRESH_EVERY": "20"},
    "permissions": {"allow": ["Bash(*)"]},
    "hooks": {"Stop": [{"matcher": "*",
                         "hooks": [{"type": "command", "command": ".claude/hooks/x.py"}]}]}
}

# t1: settings deployed to .claude/settings.json with correct content
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(SAMPLE, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "settings.json")
    if not r.passed:
        fail(f"t1: publish_settings failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: .claude/settings.json not created")
    else:
        data = json.load(open(dest))
        if data.get("env", {}).get("RABBIT_REFRESH_EVERY") == "20":
            ok("t1: settings.json deployed with correct content")
        else:
            fail(f"t1: content mismatch: {data}")

# t2: idempotent — same content reports no-op
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(SAMPLE, f)
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump(SAMPLE, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t2: idempotent call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: idempotent should report no-op, got: {r.messages}")
    else:
        ok("t2: idempotent: same content returns no-op result")

# t3: missing source → passed=False
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t3: missing source should fail")
    else:
        ok("t3: missing source → passed=False")

# t4: drift — different content overwrites destination
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    new_settings = dict(SAMPLE, env={"RABBIT_REFRESH_EVERY": "10"})
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(new_settings, f)
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump(SAMPLE, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t4: drift copy failed: {r.messages}")
    else:
        data = json.load(open(dest))
        if data.get("env", {}).get("RABBIT_REFRESH_EVERY") == "10":
            ok("t4: drift: updated source overwrites destination")
        else:
            fail(f"t4: destination not updated: {data}")

if FAIL:
    print("test-publish-settings: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-settings: all checks passed.")
