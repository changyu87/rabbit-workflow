#!/usr/bin/env python3
"""test-interpreter-value-dispatch.py — Inv 9.

Values-style dispatch: the interpreter finds the CONFIGURATION entry whose
subcommand matches argv[1], resolves values[argv[2]], dispatches the declared
mutation API, and exits 0 on success.

  t9a: human-approval false -> write_marker creates the bypass marker
  t9b: human-approval true -> delete_marker removes the bypass marker
  t9c: unknown value exits non-zero
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

HA_CONF = {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "values": {
        "true":  {"api": "delete_marker", "args": {"path": ".rabbit-human-approval-bypass"}},
        "false": {"api": "write_marker",  "args": {"path": ".rabbit-human-approval-bypass", "content": "session"}}
    },
    "default": "true",
    "alert-on": "false",
    "alert-message": {"text": "HUMAN APPROVAL BYPASS ACTIVE", "icon": "key", "color": "red"}
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


# t9a: human-approval false creates the bypass marker
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [HA_CONF])
    r = run_interpreter(td, ["human-approval", "false"])
    if r.returncode != 0:
        fail("9a", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    elif not os.path.isfile(os.path.join(td, ".rabbit-human-approval-bypass")):
        fail("9a", "bypass marker was not created")
    else:
        with open(os.path.join(td, ".rabbit-human-approval-bypass")) as f:
            content = f.read()
        if content != "session":
            fail("9a", f"marker content must be 'session', got {content!r}")
        else:
            ok("9a", "human-approval false: bypass marker created with content 'session'")

# t9b: human-approval true deletes the bypass marker
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [HA_CONF])
    marker = os.path.join(td, ".rabbit-human-approval-bypass")
    with open(marker, "w") as f:
        f.write("session")
    r = run_interpreter(td, ["human-approval", "true"])
    if r.returncode != 0:
        fail("9b", f"expected exit 0, got {r.returncode}. stderr={r.stderr!r}")
    elif os.path.isfile(marker):
        fail("9b", "bypass marker was not deleted")
    else:
        ok("9b", "human-approval true: bypass marker deleted")

# t9c: unknown value exits non-zero
with tempfile.TemporaryDirectory() as td:
    make_repo(td, [HA_CONF])
    r = run_interpreter(td, ["human-approval", "maybe"])
    if r.returncode == 0:
        fail("9c", "expected non-zero exit on unknown value 'maybe'")
    else:
        ok("9c", f"unknown value exits non-zero (rc={r.returncode})")

if FAIL:
    print("test-interpreter-value-dispatch: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-interpreter-value-dispatch: all checks passed.")
