#!/usr/bin/env python3
# test-bug-workspace-map.py
# Tests that file-bug.py and list-bugs.py use the canonical .claude/bugs/ path
# for storage and retrieval.
#
# t_wm1: file-bug.py stores bugs under .claude/bugs/ (canonical path)
# t_wm2: list-bugs.py scans bugs from .claude/bugs/ (canonical path)
# t_wm3: file-bug.py writes bug.json under .claude/bugs/<feature>/ path
# t_wm4: list-bugs.py finds bugs at the canonical .claude/bugs/ path
#
# Exit: 1 if any assertion fails.

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(FEATURE_DIR, "scripts")

passed = 0
failed = 0


def assert_pass(label):
    global passed
    print(f"PASS: {label}")
    passed += 1


def assert_fail(label, reason):
    global failed
    print(f"FAIL: {label} — {reason}")
    failed += 1


TMPDIR_ROOT = tempfile.mkdtemp()
try:
    # ---------------------------------------------------------------------------
    # Setup: isolated git repo
    # ---------------------------------------------------------------------------
    GIT_REPO = os.path.join(TMPDIR_ROOT, "test-repo")
    os.makedirs(GIT_REPO)
    subprocess.run(["git", "-C", GIT_REPO, "init", "-q"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "config", "user.name", "rabbit-test"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)

    # Ensure branch is 'main'
    r = subprocess.run(["git", "-C", GIT_REPO, "branch", "--show-current"],
                       capture_output=True, text=True)
    init_branch = r.stdout.strip()
    if init_branch != "main":
        subprocess.run(["git", "-C", GIT_REPO, "branch", "-m", init_branch, "main"],
                       check=False, capture_output=True)

    # Install find-feature.py
    rabbit_root = os.environ.get("RABBIT_ROOT")
    if not rabbit_root:
        r2 = subprocess.run(["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True)
        rabbit_root = r2.stdout.strip()

    find_feature_src = os.path.join(rabbit_root, ".claude/features/contract/scripts/find-feature.py")
    find_feature_dst_dir = os.path.join(GIT_REPO, ".claude/features/contract/scripts")
    os.makedirs(find_feature_dst_dir, exist_ok=True)
    find_feature_dst = os.path.join(find_feature_dst_dir, "find-feature.py")
    shutil.copy(find_feature_src, find_feature_dst)
    os.chmod(find_feature_dst, 0o755)

    # Create feature.json for test-feature
    test_feature_dir = os.path.join(GIT_REPO, ".claude/features/test-feature")
    os.makedirs(test_feature_dir, exist_ok=True)
    with open(os.path.join(test_feature_dir, "feature.json"), "w") as f:
        json.dump({
            "name": "test-feature",
            "version": "1.0.0",
            "owner": "test",
            "tdd_state": "test-green",
            "summary": "Test feature for workspace-map bug filing tests."
        }, f)

    BUGS_ROOT = os.path.join(GIT_REPO, ".claude/bugs")
    os.makedirs(BUGS_ROOT, exist_ok=True)

    file_bug = os.path.join(SCRIPTS_DIR, "file-bug.py")
    list_bugs = os.path.join(SCRIPTS_DIR, "list-bugs.py")

    # ---------------------------------------------------------------------------
    # t_wm1: file-bug.py stores bugs under .claude/bugs/ (canonical path)
    # ---------------------------------------------------------------------------
    T_WM1_LABEL = "t_wm1: file-bug.sh stores bugs under .claude/bugs/ (canonical path)"

    env1 = dict(os.environ, RABBIT_ROOT=GIT_REPO)
    t_wm1_exit = subprocess.run(
        [sys.executable, file_bug,
         "--title", "WM Test", "--severity", "low",
         "--description", "workspace-map test",
         "--related-feature", "test-feature"],
        cwd=GIT_REPO,
        capture_output=True,
        env=env1
    ).returncode

    bug_found1 = None
    for root, dirs, files in os.walk(BUGS_ROOT):
        for fname in files:
            if fname == "bug.json":
                bug_found1 = os.path.join(root, fname)
                break
        if bug_found1:
            break

    if bug_found1:
        assert_pass(T_WM1_LABEL)
    else:
        assert_fail(T_WM1_LABEL, f"no bug.json found under canonical path '{BUGS_ROOT}' (exit={t_wm1_exit})")

    # ---------------------------------------------------------------------------
    # t_wm2: list-bugs.py scans bugs from .claude/bugs/ (canonical path)
    # ---------------------------------------------------------------------------
    T_WM2_LABEL = "t_wm2: list-bugs.sh scans bugs from .claude/bugs/ (canonical path)"

    t_wm2_result = subprocess.run(
        [sys.executable, list_bugs, "--feature", "test-feature", "--text"],
        cwd=GIT_REPO,
        capture_output=True, text=True,
        env=env1
    )
    t_wm2_exit = t_wm2_result.returncode
    text_out = t_wm2_result.stdout + t_wm2_result.stderr

    if "TEST-FEATURE" in text_out or "WM Test" in text_out:
        assert_pass(T_WM2_LABEL)
    else:
        assert_fail(T_WM2_LABEL,
                    f"list-bugs.sh did not return expected bugs (exit={t_wm2_exit}, out='{text_out}')")

    # ---------------------------------------------------------------------------
    # t_wm3: file-bug.py writes bug.json under canonical path
    # ---------------------------------------------------------------------------
    T_WM3_LABEL = "t_wm3: file-bug.sh writes bug.json under canonical path"

    shutil.rmtree(BUGS_ROOT, ignore_errors=True)
    os.makedirs(BUGS_ROOT, exist_ok=True)

    subprocess.run(
        [sys.executable, file_bug,
         "--title", "WM Path Test", "--severity", "low",
         "--description", "path resolution test",
         "--related-feature", "test-feature"],
        cwd=GIT_REPO,
        capture_output=True,
        env=env1
    )

    bug_found3 = None
    for root, dirs, files in os.walk(BUGS_ROOT):
        for fname in files:
            if fname == "bug.json":
                bug_found3 = os.path.join(root, fname)
                break
        if bug_found3:
            break

    if bug_found3:
        assert_pass(T_WM3_LABEL)
    else:
        assert_fail(T_WM3_LABEL, f"no bug.json found under canonical path '{BUGS_ROOT}'")

    # ---------------------------------------------------------------------------
    # t_wm4: list-bugs.py finds bugs at canonical path
    # ---------------------------------------------------------------------------
    T_WM4_LABEL = "t_wm4: list-bugs.sh finds bugs at canonical .claude/bugs/ path"

    WM_BUG_DIR = os.path.join(BUGS_ROOT, "test-feature/TEST-FEATURE-WM-1")
    os.makedirs(WM_BUG_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wm_bug = {
        "name": "TEST-FEATURE-WM-1",
        "title": "WM Bug",
        "status": "open",
        "severity": "low",
        "description": "test",
        "related_feature": "test-feature",
        "filed": ts,
        "filed_by": "tester",
        "closed": None,
        "closed_by": None,
        "history": [{"ts": ts, "actor": "tester", "action": "opened", "note": "initial"}]
    }
    with open(os.path.join(WM_BUG_DIR, "bug.json"), "w") as f:
        json.dump(wm_bug, f)

    t_wm4_result = subprocess.run(
        [sys.executable, list_bugs, "--feature", "test-feature", "--text"],
        cwd=GIT_REPO,
        capture_output=True, text=True,
        env=env1
    )
    text_out2 = t_wm4_result.stdout + t_wm4_result.stderr

    if "TEST-FEATURE-WM-1" in text_out2:
        assert_pass(T_WM4_LABEL)
    else:
        assert_fail(T_WM4_LABEL,
                    f"TEST-FEATURE-WM-1 not found in list-bugs.sh output: '{text_out2}'")

finally:
    shutil.rmtree(TMPDIR_ROOT, ignore_errors=True)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("")
print(f"Results: {passed} passed, {failed} failed")

if failed > 0:
    sys.exit(1)
sys.exit(0)
