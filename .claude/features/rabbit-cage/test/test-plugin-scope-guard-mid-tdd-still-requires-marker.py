#!/usr/bin/env python3
"""E2E regression guard for Inv 17 clause (a2) interaction with the
existing per-feature marker gate (#269): a non-spec write inside a plugin
feature dir requires the scope marker. With NO marker → DENY; with the
marker → ALLOW. Confirms the spec.md carve-out is narrow.

Fixes #276.
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
FEATURE_NAME = "rabbit-cage-plugin-mid-tdd-marker-test"
SCOPE_ACTIVE = os.path.join(RUNTIME_DIR, f"scope-active-{FEATURE_NAME}")
TARGET = os.path.join(
    REPO_ROOT, ".rabbit", "rabbit-project", "features",
    FEATURE_NAME, "scripts", "foo.py",
)


@contextlib.contextmanager
def saved_state():
    paths = [MODE_FILE, SCOPE_ACTIVE]
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
    print("test-plugin-scope-guard-mid-tdd-still-requires-marker.py")
    print()
    failures = 0
    with saved_state():
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write("plugin")

        # Without marker: DENY.
        rc, stderr = run_guard(TARGET)
        if rc != 2:
            print(f"FAIL: expected DENY (rc=2) without marker for "
                  f"non-spec target, got rc={rc} stderr={stderr!r}")
            failures += 1
        else:
            print("PASS: non-spec target with no marker → DENY")

        # With marker: ALLOW.
        with open(SCOPE_ACTIVE, "w") as f:
            f.write("")
        rc2, stderr2 = run_guard(TARGET)
        if rc2 != 0:
            print(f"FAIL: expected ALLOW (rc=0) with marker for non-spec "
                  f"target, got rc={rc2} stderr={stderr2!r}")
            failures += 1
        else:
            print("PASS: non-spec target with marker → ALLOW")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
