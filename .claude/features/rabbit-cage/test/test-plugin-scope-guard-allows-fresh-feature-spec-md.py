#!/usr/bin/env python3
"""E2E test for amended Inv 17 clause (a2): plugin-mode scope-guard MUST
ALLOW writes to .rabbit/rabbit-project/features/<name>/docs/spec/spec.md
unconditionally, regardless of scope-marker state. This mirrors standalone
Inv 64 and unblocks rabbit-spec-create writing initial spec bodies to
freshly scaffolded plugin features.

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
FEATURE_NAME = "rabbit-cage-plugin-spec-md-carveout-test"
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
    print("test-plugin-scope-guard-allows-fresh-feature-spec-md.py")
    print()
    with saved_state():
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write("plugin")
        # Intentionally do NOT write scope-active-<name>: the carve-out
        # MUST ALLOW the spec.md write without any scope marker present.
        rc, stderr = run_guard(TARGET)
        if rc != 0:
            print(
                f"FAIL: expected ALLOW (rc=0) for fresh-feature spec.md "
                f"write, got rc={rc} stderr={stderr!r}"
            )
            return 1
        print("PASS: plugin-mode write to "
              ".rabbit/rabbit-project/features/<name>/docs/spec/spec.md "
              "ALLOWED with no scope marker")
    return 0


if __name__ == "__main__":
    sys.exit(main())
