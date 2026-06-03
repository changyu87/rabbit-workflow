#!/usr/bin/env python3
"""test-restart-required-emits-prompt.py — Inv 20.

Restart-required configurables surface a one-shot restart-prompt after a
successful mutation. The interpreter reads feature.json's
configuration[].restart_required flag and, on a successful mutation API
call, emits one additional yellow `rabbit_subline`-style alert containing
the literal substring `restart Claude` and the configurable's subcommand
name.

  t20a: restart_required=true + successful mutation -> stdout contains
        'restart Claude' AND the subcommand name
  t20b: restart_required absent (default False) + successful mutation ->
        stdout does NOT contain 'restart Claude' (no spurious prompt)
  t20c: restart_required=true + no-op mutation (already-applied state) ->
        stdout does NOT contain 'restart Claude' (one-shot, only on
        actual state change)
  t20d: restart_required=true + successful mutation -> the restart notice
        is rendered in red (ANSI 31) and includes the restart icon, for
        visual consistency with the rabbit banner style (issue #325).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
INTERPRETER = os.path.join(FEATURE_DIR, "skills/rabbit-config/scripts/rabbit-config.py")

# Issue #325: the restart notice must render in red (ANSI 31) and carry the
# restart icon for visual consistency with the rabbit banner style.
RED_ANSI = "\x1b[31m"
RESTART_ICON = "\U0001f504"  # 🔄

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
CONTRACT_SRC = os.path.join(REPO_ROOT, ".claude/features/contract")

# Configurable WITH restart_required flag. Uses set_json_key (cheap,
# deterministic mutation) targeting an isolated settings file inside tmp.
BP_RESTART_CONF = {
    "id": "bypass-permissions",
    "subcommand": "bypass-permissions",
    "storage": {"type": "json-key", "file": ".claude/settings.local.json", "key": "permissions.defaultMode"},
    "values": {
        "true":  {"api": "set_json_key",    "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode", "value": "bypassPermissions"}},
        "false": {"api": "delete_json_key", "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode"}},
    },
    "default": "false",
    "alert-on": "true",
    "restart_required": True,
}

# Configurable WITHOUT restart_required (regression baseline). Same shape,
# different subcommand to avoid accidental cross-contamination.
HA_NO_RESTART_CONF = {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "values": {
        "true":  {"api": "delete_marker", "args": {"path": ".rabbit-human-approval-bypass"}},
        "false": {"api": "write_marker",  "args": {"path": ".rabbit-human-approval-bypass", "content": "session"}},
    },
    "default": "true",
    "alert-on": "false",
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


# t20a: restart_required=true + successful mutation -> emits 'restart Claude'
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [BP_RESTART_CONF])
    r = run_interpreter(td, ["bypass-permissions", "true"])
    if r.returncode != 0:
        fail("20a", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    elif "restart Claude" not in r.stdout:
        fail("20a", f"expected 'restart Claude' substring in stdout, got stdout={r.stdout!r}")
    elif "bypass-permissions" not in r.stdout:
        fail("20a", f"expected 'bypass-permissions' subcommand in stdout, got stdout={r.stdout!r}")
    else:
        ok("20a", "restart_required=true: stdout contains 'restart Claude' and subcommand")

    # t20d: same successful mutation -> notice is red and carries the icon.
    if r.returncode != 0:
        fail("20d", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    elif RED_ANSI not in r.stdout:
        fail("20d", f"expected red ANSI ({RED_ANSI!r}) in restart notice, got stdout={r.stdout!r}")
    elif "\x1b[33m" in r.stdout:
        fail("20d", f"restart notice must not be yellow (ANSI 33), got stdout={r.stdout!r}")
    elif RESTART_ICON not in r.stdout:
        fail("20d", f"expected restart icon ({RESTART_ICON!r}) in restart notice, got stdout={r.stdout!r}")
    else:
        ok("20d", "restart_required=true: notice is red (ANSI 31) and includes the restart icon")

# t20b: restart_required absent (default False) -> no spurious 'restart Claude'
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [HA_NO_RESTART_CONF])
    r = run_interpreter(td, ["human-approval", "false"])
    if r.returncode != 0:
        fail("20b", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    elif "restart Claude" in r.stdout:
        fail("20b", f"unexpected 'restart Claude' substring in stdout (configurable has no restart_required flag), stdout={r.stdout!r}")
    else:
        ok("20b", "restart_required absent: stdout does NOT contain 'restart Claude'")

# t20c: restart_required=true + no-op (state already set) -> no 'restart Claude'
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [BP_RESTART_CONF])
    # Pre-seed settings.local.json with the target value so the mutation is a no-op.
    settings_dir = os.path.join(td, ".claude")
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.local.json"), "w") as f:
        json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
    r = run_interpreter(td, ["bypass-permissions", "true"])
    if r.returncode != 0:
        fail("20c", f"expected exit 0 on no-op, got {r.returncode}. stderr={r.stderr!r}")
    elif "no-op" not in r.stdout:
        fail("20c", f"expected mutation.py 'no-op' message in stdout, got stdout={r.stdout!r}")
    elif "restart Claude" in r.stdout:
        fail("20c", f"unexpected 'restart Claude' on no-op mutation, stdout={r.stdout!r}")
    else:
        ok("20c", "restart_required=true + no-op: stdout does NOT contain 'restart Claude'")

if FAIL:
    print("test-restart-required-emits-prompt: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-restart-required-emits-prompt: all checks passed.")
