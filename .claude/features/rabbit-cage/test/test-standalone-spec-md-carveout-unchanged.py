#!/usr/bin/env python3
"""E2E regression pin for standalone Inv 64: writes to a feature
spec.md (under .claude/features/<feature>/docs/spec/spec.md) in
standalone mode (no .rabbit/.runtime/mode == 'plugin' file) MUST
continue to ALLOW unconditionally. The new plugin clause (a2) is a
symmetric mirror and must not alter standalone behavior.

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
# Use an existing feature dir so find-feature.py doesn't matter here; the
# spec.md path-pattern allowlist matches on path, not feature existence.
FEATURE_NAME = "rabbit-cage-standalone-specmd-test"
TARGET = os.path.join(
    REPO_ROOT, ".claude/features", FEATURE_NAME, "docs", "spec", "spec.md",
)


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
    print("test-standalone-spec-md-carveout-unchanged.py")
    print()
    with saved_state():
        # Standalone mode: no .rabbit/.runtime/mode file.
        rc, stderr = run_guard(TARGET)
        if rc != 0:
            print(f"FAIL: expected ALLOW (rc=0) for standalone spec.md "
                  f"write, got rc={rc} stderr={stderr!r}")
            return 1
        print("PASS: standalone spec.md write ALLOWED per Inv 64 "
              "(carve-out unchanged by plugin (a2))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
