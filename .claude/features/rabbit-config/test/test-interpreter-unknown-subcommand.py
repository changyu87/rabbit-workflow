#!/usr/bin/env python3
"""test-interpreter-unknown-subcommand.py — Inv 8.

  t8a: interpreter exits non-zero on unknown subcommand
  t8b: error output names the unknown subcommand
  t8c: no-args invocation exits non-zero (usage error)
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

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


def make_repo(tmp):
    """Create minimal fake repo with contract lib and one feature."""
    features_root = os.path.join(tmp, ".claude", "features")
    os.makedirs(features_root, exist_ok=True)
    contract_dst = os.path.join(features_root, "contract")
    shutil.copytree(CONTRACT_SRC, contract_dst)
    feat_dir = os.path.join(features_root, "test-feat")
    os.makedirs(feat_dir, exist_ok=True)
    with open(os.path.join(feat_dir, "feature.json"), "w") as f:
        json.dump({
            "name": "test-feat", "version": "1.0.0", "owner": "x",
            "status": "active",
            "configuration": [{
                "id": "mode",
                "subcommand": "mode",
                "storage": {"type": "marker-file", "path": ".mode-active"},
                "values": {
                    "on": {"api": "write_marker", "args": {"path": ".mode-active", "content": "on"}},
                    "off": {"api": "delete_marker", "args": {"path": ".mode-active"}}
                },
                "default": "off"
            }]
        }, f)


def run_interpreter(tmp, args):
    return subprocess.run(
        [sys.executable, INTERPRETER, *args],
        cwd=tmp,
        capture_output=True,
        text=True
    )


# t8a: unknown subcommand exits non-zero
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    r = run_interpreter(td, ["no-such-subcommand"])
    if r.returncode == 0:
        fail("8a", f"expected non-zero exit on unknown subcommand, got 0. stdout={r.stdout!r}")
    else:
        ok("8a", f"unknown subcommand exits non-zero (rc={r.returncode})")

# t8b: error output names the unknown subcommand
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    r = run_interpreter(td, ["no-such-subcommand"])
    combined = r.stdout + r.stderr
    if "no-such-subcommand" not in combined:
        fail("8b", f"error output does not name the unknown subcommand. stderr={r.stderr!r}")
    else:
        ok("8b", "error output names the unknown subcommand")

# t8c: no-args invocation exits non-zero
with tempfile.TemporaryDirectory() as td:
    make_repo(td)
    r = run_interpreter(td, [])
    if r.returncode == 0:
        fail("8c", "expected non-zero exit on no-args invocation")
    else:
        ok("8c", "no-args invocation exits non-zero")

if FAIL:
    print("test-interpreter-unknown-subcommand: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-interpreter-unknown-subcommand: all checks passed.")
