#!/usr/bin/env python3
"""test-publish-hook.py — exercises publish_hook: deploys a hook script to
.claude/hooks/ and registers it in .claude/settings.json via read-modify-write.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_hook  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_env(td, hook_content="# hook\n"):
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    hooks_src = os.path.join(feat, "hooks")
    os.makedirs(hooks_src)
    os.makedirs(os.path.join(root, ".claude"))
    with open(os.path.join(hooks_src, "stop-check.py"), "w") as f:
        f.write(hook_content)
    return feat, root


# t1: hook file deployed to .claude/hooks/<filename>
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    r = publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "hooks", "stop-check.py")
    if not r.passed:
        fail(f"t1: publish_hook failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: hook file not deployed to .claude/hooks/")
    else:
        ok("t1: hook file deployed to .claude/hooks/")

# t2: hook registered in settings.json under correct event
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    if not os.path.isfile(settings_path):
        fail("t2: settings.json not created")
    else:
        data = json.loads(open(settings_path).read())
        stop_entries = data.get("hooks", {}).get("Stop", [])
        commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
        if ".claude/hooks/stop-check.py" in commands:
            ok("t2: hook command registered in settings.json under Stop")
        else:
            fail(f"t2: hook command not found in Stop hooks; found: {commands}")

# t3: idempotent — second call does not duplicate the settings.json entry
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    count = commands.count(".claude/hooks/stop-check.py")
    if count == 1:
        ok("t3: idempotent: duplicate call does not add duplicate settings entry")
    else:
        fail(f"t3: expected 1 registration, got {count}; commands={commands}")

# t4: existing settings.json fields are preserved (read-modify-write)
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    settings_path = os.path.join(root, ".claude", "settings.json")
    existing = {
        "env": {"MY_VAR": "hello"},
        "permissions": {"allow": ["Bash(*)"]},
        "hooks": {
            "Stop": [{"matcher": "*", "hooks": [{"type": "command",
                                                  "command": ".claude/hooks/other.py"}]}]
        }
    }
    with open(settings_path, "w") as f:
        json.dump(existing, f)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    data = json.loads(open(settings_path).read())
    if data.get("env", {}).get("MY_VAR") != "hello":
        fail("t4: existing env field lost after publish_hook")
    elif data.get("permissions", {}).get("allow") != ["Bash(*)"]:
        fail("t4: existing permissions field lost after publish_hook")
    else:
        ok("t4: existing settings fields preserved via read-modify-write")

# t5: pre-existing hook entries under same event are kept alongside new one
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    settings_path = os.path.join(root, ".claude", "settings.json")
    existing = {
        "hooks": {
            "Stop": [{"matcher": "*", "hooks": [{"type": "command",
                                                  "command": ".claude/hooks/other.py"}]}]
        }
    }
    with open(settings_path, "w") as f:
        json.dump(existing, f)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    if ".claude/hooks/other.py" not in commands:
        fail(f"t5: pre-existing hook entry was removed: {commands}")
    elif ".claude/hooks/stop-check.py" not in commands:
        fail(f"t5: new hook entry not added: {commands}")
    else:
        ok("t5: pre-existing hooks preserved; new hook added alongside")

# t6: hook registered under SessionStart event
with tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("SessionStart", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    ss_entries = data.get("hooks", {}).get("SessionStart", [])
    commands = [h["command"] for entry in ss_entries for h in entry.get("hooks", [])]
    if ".claude/hooks/stop-check.py" in commands:
        ok("t6: hook registered under SessionStart event")
    else:
        fail(f"t6: hook not registered under SessionStart: {commands}")

if FAIL:
    print("test-publish-hook: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-hook: all checks passed.")
