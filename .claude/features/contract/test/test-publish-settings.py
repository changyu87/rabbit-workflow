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


def _hook_entry(command, matcher="*"):
    return {"matcher": matcher,
            "hooks": [{"type": "command", "command": command}]}


CONTRACT_CMD = "$(git rev-parse --show-toplevel)/.claude/hooks/prompt-injector.py"
RABBIT_CAGE_CMD = "$(git rev-parse --show-toplevel)/.claude/hooks/stop-dispatcher.py"


# t5: cross-feature preservation — pre-existing hook from another feature
# MUST be preserved when a source with a different hook is published.
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    # Dest pre-populated with contract's prompt-injector Stop hook.
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump({"hooks": {"Stop": [_hook_entry(CONTRACT_CMD)]}}, f)
    # Source carries a different Stop hook (rabbit-cage's stop-dispatcher).
    src = {"hooks": {"Stop": [_hook_entry(RABBIT_CAGE_CMD)]}}
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(src, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t5: cross-feature preserve failed: {r.messages}")
    else:
        data = json.load(open(dest))
        cmds = [h.get("command") for e in data.get("hooks", {}).get("Stop", [])
                for h in e.get("hooks", [])]
        if CONTRACT_CMD in cmds and RABBIT_CAGE_CMD in cmds:
            ok("t5: cross-feature: both hooks present after merge")
        else:
            fail(f"t5: cross-feature commands missing — got {cmds}")

# t6: idempotent on repeated merges — same source twice produces no duplicates.
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump({"hooks": {"Stop": [_hook_entry(CONTRACT_CMD)]}}, f)
    src = {"hooks": {"Stop": [_hook_entry(RABBIT_CAGE_CMD)]}}
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(src, f)
    r1 = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    r2 = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not (r1.passed and r2.passed):
        fail(f"t6: idempotent calls failed: {r1.messages} {r2.messages}")
    else:
        data = json.load(open(dest))
        entries = data.get("hooks", {}).get("Stop", [])
        if len(entries) != 2:
            fail(f"t6: expected 2 Stop entries after re-merge, got {len(entries)}: {entries}")
        elif not any("no-op" in m.lower() for m in r2.messages):
            fail(f"t6: second call should be no-op, got: {r2.messages}")
        else:
            ok("t6: idempotent: re-merge yields 2 entries and no-op message")

# t7: non-hooks overwrite — source-wins for env/permissions, both hooks preserved.
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump({"env": {"X": "old"},
                   "permissions": {"allow": ["Bash(old)"]},
                   "hooks": {"Stop": [_hook_entry(CONTRACT_CMD)]}}, f)
    src = {"env": {"X": "new"},
           "permissions": {"allow": ["Bash(new)"]},
           "hooks": {"Stop": [_hook_entry(RABBIT_CAGE_CMD)]}}
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(src, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t7: non-hooks overwrite failed: {r.messages}")
    else:
        data = json.load(open(dest))
        cmds = [h.get("command") for e in data.get("hooks", {}).get("Stop", [])
                for h in e.get("hooks", [])]
        if (data.get("env", {}).get("X") == "new"
                and data.get("permissions", {}).get("allow") == ["Bash(new)"]
                and CONTRACT_CMD in cmds and RABBIT_CAGE_CMD in cmds):
            ok("t7: non-hooks source-wins; both hooks preserved")
        else:
            fail(f"t7: merge result wrong — env={data.get('env')} "
                 f"permissions={data.get('permissions')} cmds={cmds}")

# t8: empty existing hooks — dest has no 'hooks' key; source hooks merge in.
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump({"env": {"K": "v"}}, f)
    src = {"hooks": {"Stop": [_hook_entry(RABBIT_CAGE_CMD)]}}
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(src, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t8: empty-existing-hooks failed: {r.messages}")
    else:
        data = json.load(open(dest))
        cmds = [h.get("command") for e in data.get("hooks", {}).get("Stop", [])
                for h in e.get("hooks", [])]
        if data.get("env", {}).get("K") == "v" and cmds == [RABBIT_CAGE_CMD]:
            ok("t8: empty existing hooks accepts source hooks; env preserved")
        else:
            fail(f"t8: merge wrong — env={data.get('env')} cmds={cmds}")

# t9: empty source hooks — source has no 'hooks'; dest hooks survive untouched.
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(os.path.join(root, ".claude"))
    dest = os.path.join(root, ".claude", "settings.json")
    with open(dest, "w") as f:
        json.dump({"hooks": {"Stop": [_hook_entry(CONTRACT_CMD)]}}, f)
    src = {"env": {"K": "v"}}
    with open(os.path.join(feat, "settings.json"), "w") as f:
        json.dump(src, f)
    r = publish_settings("settings.json", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t9: empty-source-hooks failed: {r.messages}")
    else:
        data = json.load(open(dest))
        cmds = [h.get("command") for e in data.get("hooks", {}).get("Stop", [])
                for h in e.get("hooks", [])]
        if data.get("env", {}).get("K") == "v" and cmds == [CONTRACT_CMD]:
            ok("t9: empty source hooks leaves dest hooks intact; env applied")
        else:
            fail(f"t9: merge wrong — env={data.get('env')} cmds={cmds}")

if FAIL:
    print("test-publish-settings: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-settings: all checks passed.")
