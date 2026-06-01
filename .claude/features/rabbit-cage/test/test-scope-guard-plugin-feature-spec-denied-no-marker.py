#!/usr/bin/env python3
"""E2E test for amended Inv 17(a): plugin-mode scope-guard MUST deny
writes to .rabbit/rabbit-project/features/<name>/** with the structured
three-option DENY message when no scope-active-<name> marker is present.

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
FEATURE_NAME = "rabbit-cage-plugin-feature-denied-test"
SCOPE_ACTIVE = os.path.join(RUNTIME_DIR, f"scope-active-{FEATURE_NAME}")
TARGET = os.path.join(
    REPO_ROOT, ".rabbit", "rabbit-project", "features",
    FEATURE_NAME, "docs", "spec", "spec.md",
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
    print("test-scope-guard-plugin-feature-spec-denied-no-marker.py")
    print()
    failures = 0
    with saved_state():
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write("plugin")
        # Intentionally do NOT write scope-active-<name>.
        rc, stderr = run_guard(TARGET)
        if rc != 2:
            print(f"FAIL: expected DENY (rc=2), got rc={rc} stderr={stderr!r}")
            return 1
        print(f"PASS: rc=2 (DENY) for .rabbit/rabbit-project/features/"
              f"{FEATURE_NAME}/... with no marker")
        # Structured DENY message MUST name the feature and the target path
        # plus the three-option block (SESSION OVERRIDE, ONE-TIME OVERRIDE,
        # rabbit-feature-touch).
        for needle in (FEATURE_NAME, TARGET, "DENY", "SESSION OVERRIDE",
                       "ONE-TIME OVERRIDE", "rabbit-feature-touch"):
            if needle in stderr:
                print(f"PASS: DENY message contains {needle!r}")
            else:
                print(f"FAIL: DENY message missing {needle!r}: {stderr!r}")
                failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
