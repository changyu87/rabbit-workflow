#!/usr/bin/env python3
"""test-interpreter-action-dispatch.py — Inv 10.

Actions-style dispatch: the interpreter finds the CONFIGURATION entry,
resolves actions[argv[2]], dispatches the mutation API, and exits 0.

  t10a: allowed-tools add appends value to JSON array
  t10b: allowed-tools remove removes value from JSON array
  t10c: unknown action exits non-zero
  t10d: bypass-permissions true -> set_json_key writes bypassPermissions
  t10e: bypass-permissions false -> delete_json_key removes the key
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
INTERPRETER = os.path.join(FEATURE_DIR, "skills/rabbit-config/scripts/rabbit-config.py")

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
CONTRACT_SRC = os.path.join(REPO_ROOT, ".claude/features/contract")

AT_CONF = {
    "id": "allowed-tools",
    "subcommand": "allowed-tools",
    "storage": {"type": "json-array", "file": ".claude/settings.local.json", "key": "permissions.allow"},
    "actions": {
        "add":    {"api": "append_json_array",       "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "{tool}"}},
        "remove": {"api": "remove_json_array_value", "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "{tool}"}}
    },
    "validation": {"reject_prefix": "Bash("}
}

BP_CONF = {
    "id": "bypass-permissions",
    "subcommand": "bypass-permissions",
    "storage": {"type": "json-key", "file": ".claude/settings.local.json", "key": "permissions.defaultMode"},
    "values": {
        "true":  {"api": "set_json_key",   "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode", "value": "bypassPermissions"}},
        "false": {"api": "delete_json_key", "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode"}}
    },
    "default": "false",
    "alert-on": "true",
    "alert-message": {"text": "BYPASS-PERMISSIONS MODE ACTIVE", "icon": "siren", "color": "red"}
}

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


def make_repo(tmp, configuration):
    features_root = os.path.join(tmp, ".claude", "features")
    os.makedirs(features_root, exist_ok=True)
    shutil.copytree(CONTRACT_SRC, os.path.join(features_root, "contract"))
    feat_dir = os.path.join(features_root, "rabbit-cage")
    os.makedirs(feat_dir, exist_ok=True)
    with open(os.path.join(feat_dir, "feature.json"), "w") as f:
        json.dump({"name": "rabbit-cage", "version": "1.0.0", "owner": "x",
                   "status": "active", "configuration": configuration}, f)


def run_interpreter(tmp, args):
    return subprocess.run(
        [sys.executable, INTERPRETER, *args],
        cwd=tmp, capture_output=True, text=True
    )


def read_json_key(path, dotted_key):
    """Read value at dotted_key from JSON file; returns None if absent."""
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        data = json.load(f)
    for part in dotted_key.split("."):
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


# t10a: allowed-tools add appends to JSON array
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    r = run_interpreter(td, ["allowed-tools", "add", "Write"])
    if r.returncode != 0:
        fail("10a", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    else:
        allow = read_json_key(os.path.join(td, ".claude/settings.local.json"), "permissions.allow")
        if "Write" not in (allow or []):
            fail("10a", f"'Write' not in permissions.allow after add; got {allow!r}")
        else:
            ok("10a", "allowed-tools add appends tool to permissions.allow")

# t10b: allowed-tools remove removes from JSON array
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    settings_path = os.path.join(td, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump({"permissions": {"allow": ["Read", "Write"]}}, f)
    r = run_interpreter(td, ["allowed-tools", "remove", "Write"])
    if r.returncode != 0:
        fail("10b", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    else:
        allow = read_json_key(settings_path, "permissions.allow")
        if "Write" in (allow or []):
            fail("10b", f"'Write' still in permissions.allow after remove; got {allow!r}")
        elif "Read" not in (allow or []):
            fail("10b", f"'Read' was incorrectly removed; got {allow!r}")
        else:
            ok("10b", "allowed-tools remove removes tool from permissions.allow, preserves others")

# t10c: unknown action exits non-zero
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    r = run_interpreter(td, ["allowed-tools", "replace", "Write"])
    if r.returncode == 0:
        fail("10c", "expected non-zero exit on unknown action 'replace'")
    else:
        ok("10c", f"unknown action exits non-zero (rc={r.returncode})")

# t10d: bypass-permissions true -> set_json_key writes bypassPermissions
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [BP_CONF])
    r = run_interpreter(td, ["bypass-permissions", "true"])
    if r.returncode != 0:
        fail("10d", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    else:
        settings_path = os.path.join(td, ".claude/settings.local.json")
        mode = read_json_key(settings_path, "permissions.defaultMode")
        if mode != "bypassPermissions":
            fail("10d", f"permissions.defaultMode must be 'bypassPermissions', got {mode!r}")
        else:
            ok("10d", "bypass-permissions true: defaultMode set to 'bypassPermissions'")

# t10e: bypass-permissions false -> delete_json_key removes the key
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [BP_CONF])
    settings_path = os.path.join(td, ".claude/settings.local.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions", "allow": ["Read"]}}, f)
    r = run_interpreter(td, ["bypass-permissions", "false"])
    if r.returncode != 0:
        fail("10e", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    else:
        mode = read_json_key(settings_path, "permissions.defaultMode")
        if mode is not None:
            fail("10e", f"permissions.defaultMode must be absent after false, got {mode!r}")
        elif read_json_key(settings_path, "permissions.allow") != ["Read"]:
            fail("10e", "sibling key 'allow' was incorrectly affected")
        else:
            ok("10e", "bypass-permissions false: defaultMode removed, sibling keys preserved")

if FAIL:
    print("test-interpreter-action-dispatch: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-interpreter-action-dispatch: all checks passed.")
