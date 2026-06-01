#!/usr/bin/env python3
"""Regression test for amended Inv 17(a): the .rabbit/.claude/** always-DENY
clause MUST remain intact after the carve-out narrowing. The rabbit-project
carve-out applies ONLY to .rabbit/rabbit-project/features/<name>/**.

Fixes #269.
"""
import contextlib
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")

RUNTIME_DIR = os.path.join(REPO_ROOT, ".rabbit", ".runtime")
MODE_FILE = os.path.join(RUNTIME_DIR, "mode")
TARGET = os.path.join(REPO_ROOT, ".rabbit", ".claude", "hooks", "x.py")


@contextlib.contextmanager
def saved_state():
    paths = [MODE_FILE]
    saved = {}
    for p in paths:
        if os.path.isfile(p):
            with open(p, "rb") as f:
                saved[p] = f.read()
            os.remove(p)
    try:
        yield
    finally:
        for p in paths:
            if os.path.isfile(p):
                os.remove(p)
        for p, content in saved.items():
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(content)


def run_guard(target_path):
    payload = {"tool_name": "Write",
               "tool_input": {"file_path": target_path, "content": "x"}}
    result = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return result.returncode, result.stderr


def main():
    print("test-scope-guard-plugin-claude-still-denied.py")
    print()
    with saved_state():
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write("plugin")
        rc, stderr = run_guard(TARGET)
        if rc == 2 and "DENY" in stderr:
            print("PASS: .rabbit/.claude/** still DENIES in plugin mode")
            return 0
        print(f"FAIL: expected DENY (rc=2), got rc={rc} stderr={stderr!r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
