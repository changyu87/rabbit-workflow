#!/usr/bin/env python3
"""test-publish-hook.py — exercises publish_hook: deploys a hook script to
.claude/hooks/ and registers it in .claude/settings.json via read-modify-write.
"""

import json
import os
import sys
import tempfile
from unittest.mock import patch

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_hook  # noqa: E402

FAIL = 0


def _standalone_env():
    """Context manager that removes RABBIT_ROOT so standalone form is selected.

    Per Inv 42, publish_hook selects plugin form when RABBIT_ROOT is set in
    os.environ. The standalone-form assertions below MUST run with RABBIT_ROOT
    unset; otherwise a leaked parent env value flips the form unexpectedly.
    """
    env = dict(os.environ)
    env.pop("RABBIT_ROOT", None)
    return patch.dict(os.environ, env, clear=True)


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
with _standalone_env(), tempfile.TemporaryDirectory() as td:
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
with _standalone_env(), tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    if not os.path.isfile(settings_path):
        fail("t2: settings.json not created")
    else:
        data = json.loads(open(settings_path).read())
        stop_entries = data.get("hooks", {}).get("Stop", [])
        commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
        if "$(git rev-parse --show-toplevel)/.claude/hooks/stop-check.py" in commands:
            ok("t2: hook command registered in settings.json under Stop")
        else:
            fail(f"t2: hook command not found in Stop hooks; found: {commands}")

# t3: idempotent — second call does not duplicate the settings.json entry
with _standalone_env(), tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    count = commands.count("$(git rev-parse --show-toplevel)/.claude/hooks/stop-check.py")
    if count == 1:
        ok("t3: idempotent: duplicate call does not add duplicate settings entry")
    else:
        fail(f"t3: expected 1 registration, got {count}; commands={commands}")

# t4: existing settings.json fields are preserved (read-modify-write)
with _standalone_env(), tempfile.TemporaryDirectory() as td:
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
with _standalone_env(), tempfile.TemporaryDirectory() as td:
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
    elif "$(git rev-parse --show-toplevel)/.claude/hooks/stop-check.py" not in commands:
        fail(f"t5: new hook entry not added: {commands}")
    else:
        ok("t5: pre-existing hooks preserved; new hook added alongside")

# t6: hook registered under SessionStart event
with _standalone_env(), tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("SessionStart", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    ss_entries = data.get("hooks", {}).get("SessionStart", [])
    commands = [h["command"] for entry in ss_entries for h in entry.get("hooks", [])]
    if "$(git rev-parse --show-toplevel)/.claude/hooks/stop-check.py" in commands:
        ok("t6: hook registered under SessionStart event")
    else:
        fail(f"t6: hook not registered under SessionStart: {commands}")

# t-new-form (t7): registered command literally starts with $(git rev-parse
# --show-toplevel)/ in standalone mode (RABBIT_ROOT unset). Regression guard
# against accidental reversion to a bare relative path (Inv 42).
with _standalone_env(), tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    matching = [c for c in commands if c.endswith("/stop-check.py")]
    if not matching:
        fail(f"t-new-form: no stop-check.py command found in Stop entries: {commands}")
    elif not all(c.startswith("$(git rev-parse --show-toplevel)/") for c in matching):
        fail(f"t-new-form: command does not start with $(git rev-parse --show-toplevel)/: {matching}")
    else:
        ok("t-new-form: registered command starts with $(git rev-parse --show-toplevel)/")

# t-migration (t8): pre-seeded legacy bare-relative entry is upgraded in place,
# not duplicated. Exactly one entry remains under Stop for stop-check.py and
# its command is the new standalone form (RABBIT_ROOT unset).
with _standalone_env(), tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    settings_path = os.path.join(root, ".claude", "settings.json")
    existing = {
        "hooks": {
            "Stop": [{"matcher": "*", "hooks": [{"type": "command",
                                                  "command": ".claude/hooks/stop-check.py"}]}]
        }
    }
    with open(settings_path, "w") as f:
        json.dump(existing, f)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    new_form = "$(git rev-parse --show-toplevel)/.claude/hooks/stop-check.py"
    legacy_form = ".claude/hooks/stop-check.py"
    stop_check_entries = [c for c in commands if c.endswith("/stop-check.py") or c == legacy_form]
    if len(stop_check_entries) != 1:
        fail(f"t-migration: expected exactly 1 stop-check.py entry after migration, got {len(stop_check_entries)}: {stop_check_entries}")
    elif stop_check_entries[0] != new_form:
        fail(f"t-migration: migrated entry is not new form; got: {stop_check_entries[0]!r}")
    elif legacy_form in commands:
        fail(f"t-migration: legacy bare-relative entry still present after migration: {commands}")
    else:
        ok("t-migration: legacy entry migrated in place to new form (no duplicate)")

# t-plugin-form (Inv 42): when RABBIT_ROOT is set in os.environ, publish_hook
# MUST emit the plugin-form command literal `$RABBIT_ROOT/.claude/hooks/<name>`
# (NOT an expanded path). /bin/sh substitutes the env var at hook-fire time.
plugin_env = dict(os.environ)
plugin_env["RABBIT_ROOT"] = "/tmp/fake-install"
with patch.dict(os.environ, plugin_env, clear=True), tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    expected = "$RABBIT_ROOT/.claude/hooks/stop-check.py"
    if expected in commands:
        ok("t-plugin-form: registered command is literal $RABBIT_ROOT/.claude/hooks/<name>")
    else:
        fail(f"t-plugin-form: expected literal {expected!r} in commands; got: {commands}")

# t-plugin-idempotent (Inv 42): in plugin mode, two consecutive publish_hook
# calls produce exactly one hook entry and the second call is a no-op.
with patch.dict(os.environ, plugin_env, clear=True), tempfile.TemporaryDirectory() as td:
    feat, root = make_env(td)
    publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    r2 = publish_hook("Stop", "hooks/stop-check.py", feature_dir=feat, repo_root=root)
    settings_path = os.path.join(root, ".claude", "settings.json")
    data = json.loads(open(settings_path).read())
    stop_entries = data.get("hooks", {}).get("Stop", [])
    commands = [h["command"] for entry in stop_entries for h in entry.get("hooks", [])]
    expected = "$RABBIT_ROOT/.claude/hooks/stop-check.py"
    count = commands.count(expected)
    if count != 1:
        fail(f"t-plugin-idempotent: expected 1 plugin-form entry, got {count}; commands={commands}")
    elif not r2.passed:
        fail(f"t-plugin-idempotent: second call failed: {r2.messages}")
    elif not any("no-op" in m for m in r2.messages):
        fail(f"t-plugin-idempotent: second call not reported as no-op: {r2.messages}")
    else:
        ok("t-plugin-idempotent: re-running in plugin mode is a no-op (no duplicates)")

if FAIL:
    print("test-publish-hook: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-hook: all checks passed.")
