#!/usr/bin/env python3
# test-dispatch.py — verify dispatch-feature-edit.py output.
# Non-interactive. Exits non-zero on failure.

import os
import sys
import subprocess
import tempfile
import shutil
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = os.environ.get("RABBIT_ROOT", result.stdout.strip() if result.returncode == 0 else "")

FAIL = 0

# The dispatch script computes REPO_ROOT as 4 levels up from its scripts/ dir.
# With structure: FAKE_REPO/.claude/features/contract/scripts,
# 4 ups from scripts = FAKE_REPO — which is also where feature.json files live.
FAKE_ROOT = tempfile.mkdtemp(prefix="rbt-dispatch-", dir="/tmp")
FAKE_REPO = os.path.join(FAKE_ROOT, "rabbit-run")


def cleanup():
    shutil.rmtree(FAKE_ROOT, ignore_errors=True)


try:
    FAKE_SCRIPTS = os.path.join(FAKE_REPO, ".claude/features/contract/scripts")
    FAKE_POLICY_DIR = os.path.join(FAKE_REPO, ".claude/features/policy")

    for d in [
        FAKE_SCRIPTS,
        os.path.join(FAKE_REPO, ".claude/features"),
        os.path.join(FAKE_REPO, ".claude/features/auto-refresh/docs/spec"),
        os.path.join(FAKE_REPO, ".claude"),
        FAKE_POLICY_DIR,
    ]:
        os.makedirs(d, exist_ok=True)

    # Copy scripts — policy-block.py and find-feature.py must be adjacent to dispatch-feature-edit.py.
    for script_name in ["policy-block.py", "dispatch-feature-edit.py", "find-feature.py"]:
        src = os.path.join(FEATURE_DIR, "scripts", script_name)
        dst = os.path.join(FAKE_SCRIPTS, script_name)
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)

    # policy-block.py reads policy files from REPO_ROOT/.claude/features/policy/
    REAL_POLICY_DIR = os.path.join(REPO_ROOT, ".claude/features/policy") if REPO_ROOT else ""
    if REAL_POLICY_DIR and os.path.isdir(REAL_POLICY_DIR):
        for f in ["philosophy.md", "spec-rules.md", "coding-rules.md"]:
            src = os.path.join(REAL_POLICY_DIR, f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(FAKE_POLICY_DIR, f))

    # Install a feature.json for the test feature so find-feature.py can discover it.
    os.makedirs(os.path.join(FAKE_REPO, ".claude/features/auto-refresh"), exist_ok=True)
    feature_data = {
        "name": "auto-refresh",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "Test entry for dispatch test."
    }
    with open(os.path.join(FAKE_REPO, ".claude/features/auto-refresh/feature.json"), "w") as f:
        json.dump(feature_data, f, indent=2)

    env = os.environ.copy()
    env["RABBIT_ROOT"] = FAKE_REPO

    proc = subprocess.run(
        ["python3", os.path.join(FAKE_SCRIPTS, "dispatch-feature-edit.py"),
         "auto-refresh", "test task description"],
        capture_output=True, text=True, env=env
    )
    STDOUT = proc.stdout
    STDERR = proc.stderr
    ACTUAL_EXIT = proc.returncode

    # Test 1: exits 0.
    if ACTUAL_EXIT != 0:
        print(f"FAIL: dispatch-feature-edit.py exited {ACTUAL_EXIT} (expected 0)", file=sys.stderr)
        print(f"  STDERR: {STDERR}", file=sys.stderr)
        FAIL = 1

    def check_stdout(label, pattern):
        global FAIL
        if pattern not in STDOUT:
            print(f"FAIL [{label}]: stdout does not contain: {pattern}", file=sys.stderr)
            FAIL = 1

    # Test 2: stdout contains sentinel.
    check_stdout("sentinel", "RABBIT-POLICY-BLOCK-v1")

    # Test 3: stdout contains SCOPE: auto-refresh.
    check_stdout("scope-line", "SCOPE: auto-refresh")

    # Test 4: stdout contains task description.
    check_stdout("task-desc", "test task description")

    # Test 5: stderr does NOT contain [stub].
    if "[stub]" in STDERR:
        print(f"FAIL [no-stub-in-stderr]: stderr contains '[stub]': {STDERR}", file=sys.stderr)
        FAIL = 1

    # t-rr1: Verify output contains "SCOPE: auto-refresh" (feature-found signal).
    if "SCOPE: auto-refresh" not in STDOUT:
        print("FAIL [t-rr1]: SCOPE line absent — REPO_ROOT likely wrong (feature not found by find-feature.py)", file=sys.stderr)
        FAIL = 1
    else:
        print("t-rr1: PASS (SCOPE: auto-refresh present — feature resolved correctly)")

    # t-rr2: Verify the script's REPO_ROOT computation: git rev-parse from the
    # scripts dir inside the real repo equals repo root.
    if REPO_ROOT:
        REAL_SCRIPTS_DIR = os.path.join(REPO_ROOT, ".claude/features/contract/scripts")
        r2 = subprocess.run(
            ["git", "-C", REAL_SCRIPTS_DIR, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        COMPUTED_ROOT = r2.stdout.strip() if r2.returncode == 0 else ""
        if COMPUTED_ROOT != REPO_ROOT:
            print(f"FAIL [t-rr2]: REPO_ROOT mismatch — got '{COMPUTED_ROOT}', want '{REPO_ROOT}'", file=sys.stderr)
            FAIL = 1
        else:
            print(f"t-rr2: PASS (git rev-parse from scripts resolves to repo root: {COMPUTED_ROOT})")

finally:
    cleanup()

if FAIL != 0:
    print("test-dispatch: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-dispatch: all checks passed.")
