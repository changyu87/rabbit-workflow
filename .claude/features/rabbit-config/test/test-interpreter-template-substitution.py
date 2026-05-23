#!/usr/bin/env python3
"""test-interpreter-template-substitution.py — Inv 11.

Template substitution: {tool} and {command} placeholders in API args are
replaced with the caller-provided extra argument before dispatch.

  t11a: {tool} placeholder is replaced with the extra arg value
  t11b: {command} placeholder is replaced (bash-allow pattern)
  t11c: actions without template work with two args (no extra arg needed)
  t11d: action with template and missing extra arg exits non-zero
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

BA_CONF = {
    "id": "bash-allow",
    "subcommand": "bash-allow",
    "storage": {"type": "json-array-templated", "file": ".claude/settings.local.json", "key": "permissions.allow", "template": "Bash({value}:*)"},
    "actions": {
        "add":    {"api": "append_json_array",       "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "Bash({command}:*)"}},
        "remove": {"api": "remove_json_array_value", "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "Bash({command}:*)"}}
    },
    "validation": {"reject_chars": "():\\s"}
}

SIMPLE_ACTION_CONF = {
    "id": "simple-action",
    "subcommand": "simple-action",
    "actions": {
        "on":  {"api": "write_marker", "args": {"path": ".simple-on", "content": "on"}},
        "off": {"api": "delete_marker", "args": {"path": ".simple-on"}}
    }
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


def read_json_array(path, dotted_key):
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        data = json.load(f)
    for part in dotted_key.split("."):
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


# t11a: {tool} placeholder replaced with extra arg
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    r = run_interpreter(td, ["allowed-tools", "add", "MyTool"])
    settings_path = os.path.join(td, ".claude/settings.local.json")
    if r.returncode != 0:
        fail("11a", f"exit {r.returncode}. stderr={r.stderr!r}")
    else:
        allow = read_json_array(settings_path, "permissions.allow")
        if "MyTool" not in (allow or []):
            fail("11a", f"'MyTool' (literal, not '{{tool}}') not in permissions.allow; got {allow!r}")
        elif "{tool}" in (allow or []):
            fail("11a", "literal '{{tool}}' found in permissions.allow (template not substituted)")
        else:
            ok("11a", "{tool} placeholder substituted with 'MyTool'")

# t11b: {command} placeholder replaced (bash-allow pattern)
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [BA_CONF])
    r = run_interpreter(td, ["bash-allow", "add", "git"])
    settings_path = os.path.join(td, ".claude/settings.local.json")
    if r.returncode != 0:
        fail("11b", f"exit {r.returncode}. stderr={r.stderr!r}")
    else:
        allow = read_json_array(settings_path, "permissions.allow")
        if "Bash(git:*)" not in (allow or []):
            fail("11b", f"'Bash(git:*)' not in permissions.allow; got {allow!r}")
        elif "Bash({command}:*)" in (allow or []):
            fail("11b", "literal 'Bash({{command}}:*)' in permissions.allow (template not substituted)")
        else:
            ok("11b", "{command} placeholder substituted, producing 'Bash(git:*)'")

# t11c: action without template works with two args only
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [SIMPLE_ACTION_CONF])
    r = run_interpreter(td, ["simple-action", "on"])
    if r.returncode != 0:
        fail("11c", f"expected exit 0 for no-template action with 2 args, got {r.returncode}. stderr={r.stderr!r}")
    elif not os.path.isfile(os.path.join(td, ".simple-on")):
        fail("11c", "marker not created by no-template action")
    else:
        ok("11c", "no-template action works with exactly 2 args")

# t11d: action with template and missing extra arg exits non-zero
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    r = run_interpreter(td, ["allowed-tools", "add"])
    if r.returncode == 0:
        fail("11d", "expected non-zero exit when template arg is required but missing")
    else:
        ok("11d", f"missing template arg exits non-zero (rc={r.returncode})")

if FAIL:
    print("test-interpreter-template-substitution: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-interpreter-template-substitution: all checks passed.")
