#!/usr/bin/env python3
"""test-interpreter-validation.py — Inv 12–15.

Input validation per the validation field on each CONFIGURATION entry.

  t12a: reject_prefix: arg starting with the prefix is rejected (exit non-zero)
  t12b: reject_prefix: arg not starting with the prefix is accepted
  t13a: reject_chars: arg containing forbidden char is rejected (exit non-zero)
  t13b: reject_chars: arg without forbidden chars is accepted
  t14:  values-style subcommand with unknown value: exits non-zero
  t15:  actions-style subcommand with unknown action: exits non-zero
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

HA_CONF = {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "values": {
        "true":  {"api": "delete_marker", "args": {"path": ".rabbit-human-approval-bypass"}},
        "false": {"api": "write_marker",  "args": {"path": ".rabbit-human-approval-bypass", "content": "session"}}
    },
    "default": "true"
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


# t12a: reject_prefix: "Bash(foo:*)" starts with "Bash(" -> rejected
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    r = run_interpreter(td, ["allowed-tools", "add", "Bash(ls:*)"])
    if r.returncode == 0:
        fail("12a", "expected rejection of value starting with 'Bash(', got exit 0")
    else:
        ok("12a", f"reject_prefix 'Bash(': 'Bash(ls:*)' rejected (rc={r.returncode})")

# t12b: reject_prefix: "Write" does not start with "Bash(" -> accepted
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    r = run_interpreter(td, ["allowed-tools", "add", "Write"])
    if r.returncode != 0:
        fail("12b", f"expected acceptance of 'Write', got exit {r.returncode}. stderr={r.stderr!r}")
    else:
        ok("12b", "reject_prefix: 'Write' is accepted (no prefix match)")

# t13a: reject_chars: "git status" contains space -> rejected
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [BA_CONF])
    r = run_interpreter(td, ["bash-allow", "add", "git status"])
    if r.returncode == 0:
        fail("13a", "expected rejection of value with space, got exit 0")
    else:
        ok("13a", f"reject_chars '():\\\\s': 'git status' (space) rejected (rc={r.returncode})")

# t13b: reject_chars: "git" has no forbidden chars -> accepted
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [BA_CONF])
    r = run_interpreter(td, ["bash-allow", "add", "git"])
    if r.returncode != 0:
        fail("13b", f"expected acceptance of 'git', got exit {r.returncode}. stderr={r.stderr!r}")
    else:
        ok("13b", "reject_chars: 'git' is accepted (no forbidden chars)")

# t14: values-style subcommand with unknown value exits non-zero
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [HA_CONF])
    r = run_interpreter(td, ["human-approval", "maybe"])
    if r.returncode == 0:
        fail("14", "expected non-zero on unknown value 'maybe'")
    else:
        ok("14", f"unknown value exits non-zero (rc={r.returncode})")

# t15: actions-style subcommand with unknown action exits non-zero
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [AT_CONF])
    r = run_interpreter(td, ["allowed-tools", "replace", "Write"])
    if r.returncode == 0:
        fail("15", "expected non-zero on unknown action 'replace'")
    else:
        ok("15", f"unknown action exits non-zero (rc={r.returncode})")

if FAIL:
    print("test-interpreter-validation: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-interpreter-validation: all checks passed.")
