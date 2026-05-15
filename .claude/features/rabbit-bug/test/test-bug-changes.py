#!/usr/bin/env python3
# test-bug-changes.py
# Failing tests for pending changes to the rabbit-bug feature.
#
# t_bug1: --reason accepted (replaces --note) — transition succeeds with --reason
# t_bug2: --note alone (without --reason) exits non-zero
# t_bug3: --reason is required on set — omitting it exits non-zero
# t_bug4: --fix-commits required on closed — missing --fix-commits (and no --skip-vet-reason) exits non-zero
# t_bug5: --fix-commits accepted on closed — transition succeeds when provided
# t_bug6: --fix-commits rejected on refused — providing it exits non-zero
# t_bug7: git commit created after successful set transition
# t_bug8: git commit created after file-bug.py creates a bug
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
    # Setup: create a temp git repo and a fresh bug for tests that need one
    # ---------------------------------------------------------------------------
    GIT_REPO = os.path.join(TMPDIR_ROOT, "test-repo")
    os.makedirs(GIT_REPO)
    subprocess.run(["git", "-C", GIT_REPO, "init", "-q"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "config", "user.name", "Test User"], check=True)

    # Make initial commit so git log works
    readme = os.path.join(GIT_REPO, "README")
    open(readme, "w").close()
    subprocess.run(["git", "-C", GIT_REPO, "add", "README"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "commit", "-q", "-m", "init"], check=True)

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
        r2 = subprocess.run(["git", "-C", SCRIPTS_DIR, "rev-parse", "--show-toplevel"],
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
            "summary": "Test feature for bug changes tests."
        }, f)

    bug_status = os.path.join(SCRIPTS_DIR, "bug-status.py")
    file_bug = os.path.join(SCRIPTS_DIR, "file-bug.py")

    def make_bug_dir(bug_dir):
        os.makedirs(bug_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        bug = {
            "name": "TEST-BUG-1",
            "title": "Test Bug",
            "status": "open",
            "severity": "low",
            "description": "test desc",
            "related_feature": "test-feature",
            "filed": ts,
            "filed_by": "tester",
            "closed": None,
            "closed_by": None,
            "history": [{"ts": ts, "actor": "tester", "action": "opened", "note": "initial filing"}]
        }
        with open(os.path.join(bug_dir, "bug.json"), "w") as f:
            json.dump(bug, f)

    # ---------------------------------------------------------------------------
    # t_bug1: --reason accepted (replaces --note) — transition succeeds with --reason
    # ---------------------------------------------------------------------------
    T_BUG1_LABEL = "t_bug1: --reason accepted (replaces --note) — transition succeeds with --reason"
    BUG1_DIR = os.path.join(TMPDIR_ROOT, "bug1")
    make_bug_dir(BUG1_DIR)

    t_bug1_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG1_DIR, "refused",
         "--reason", "test reason", "--skip-vet-reason", "bypass"],
        capture_output=True
    ).returncode

    if t_bug1_exit == 0:
        assert_pass(T_BUG1_LABEL)
    else:
        assert_fail(T_BUG1_LABEL, f"bug-status.sh set with --reason exited {t_bug1_exit} (expected 0)")

    # ---------------------------------------------------------------------------
    # t_bug2: --note alone (without --reason) exits non-zero
    # ---------------------------------------------------------------------------
    T_BUG2_LABEL = "t_bug2: --note alone (without --reason) exits non-zero"
    BUG2_DIR = os.path.join(TMPDIR_ROOT, "bug2")
    make_bug_dir(BUG2_DIR)

    t_bug2_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG2_DIR, "refused",
         "--note", "old note", "--skip-vet-reason", "bypass"],
        capture_output=True
    ).returncode

    if t_bug2_exit != 0:
        assert_pass(T_BUG2_LABEL)
    else:
        assert_fail(T_BUG2_LABEL, "bug-status.sh set with --note exited 0 (expected non-zero; --note should be rejected)")

    # ---------------------------------------------------------------------------
    # t_bug3: --reason is required on set — omitting it exits non-zero
    # ---------------------------------------------------------------------------
    T_BUG3_LABEL = "t_bug3: --reason required on set — omitting it exits non-zero"
    BUG3_DIR = os.path.join(TMPDIR_ROOT, "bug3")
    make_bug_dir(BUG3_DIR)

    t_bug3_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG3_DIR, "refused",
         "--skip-vet-reason", "bypass"],
        capture_output=True
    ).returncode

    if t_bug3_exit != 0:
        assert_pass(T_BUG3_LABEL)
    else:
        assert_fail(T_BUG3_LABEL, "bug-status.sh set without --reason exited 0 (expected non-zero)")

    # ---------------------------------------------------------------------------
    # t_bug4: --fix-commits required on closed — missing it exits non-zero
    # ---------------------------------------------------------------------------
    T_BUG4_LABEL = "t_bug4: --fix-commits required on closed — missing it exits non-zero"
    BUG4_DIR = os.path.join(TMPDIR_ROOT, "bug4")
    make_bug_dir(BUG4_DIR)

    t_bug4_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG4_DIR, "closed",
         "--note", "closing it", "--skip-vet-reason", "bypass"],
        capture_output=True
    ).returncode

    if t_bug4_exit != 0:
        assert_pass(T_BUG4_LABEL)
    else:
        assert_fail(T_BUG4_LABEL, "bug-status.sh set closed without --fix-commits exited 0 (expected non-zero)")

    # ---------------------------------------------------------------------------
    # t_bug5: --fix-commits accepted on closed — transition succeeds when provided
    # ---------------------------------------------------------------------------
    T_BUG5_LABEL = "t_bug5: --fix-commits accepted on closed — transition succeeds when provided"
    BUG5_DIR = os.path.join(TMPDIR_ROOT, "bug5")
    make_bug_dir(BUG5_DIR)

    t_bug5_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG5_DIR, "closed",
         "--reason", "fixed it", "--fix-commits", "abc123",
         "--skip-vet-reason", "bypass"],
        capture_output=True
    ).returncode

    if t_bug5_exit == 0:
        assert_pass(T_BUG5_LABEL)
    else:
        assert_fail(T_BUG5_LABEL, f"bug-status.sh set closed with --fix-commits exited {t_bug5_exit} (expected 0)")

    # ---------------------------------------------------------------------------
    # t_bug6: --fix-commits rejected on refused — providing it exits non-zero
    # ---------------------------------------------------------------------------
    T_BUG6_LABEL = "t_bug6: --fix-commits rejected on refused — providing it exits non-zero"
    BUG6_DIR = os.path.join(TMPDIR_ROOT, "bug6")
    make_bug_dir(BUG6_DIR)

    t_bug6_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG6_DIR, "refused",
         "--note", "wontfix", "--fix-commits", "abc123",
         "--skip-vet-reason", "bypass"],
        capture_output=True
    ).returncode

    if t_bug6_exit != 0:
        assert_pass(T_BUG6_LABEL)
    else:
        assert_fail(T_BUG6_LABEL, "bug-status.sh set refused with --fix-commits exited 0 (expected non-zero)")

    # ---------------------------------------------------------------------------
    # t_bug7: git commit created after successful set transition
    # ---------------------------------------------------------------------------
    T_BUG7_LABEL = "t_bug7: git commit created after successful set transition"

    BUG7_ROOT = os.path.join(GIT_REPO, ".claude/bugs/test-feature")
    os.makedirs(BUG7_ROOT, exist_ok=True)
    BUG7_DIR = os.path.join(BUG7_ROOT, "TEST-FEATURE-1")
    make_bug_dir(BUG7_DIR)
    subprocess.run(["git", "-C", GIT_REPO, "add", os.path.join(BUG7_DIR, "bug.json")], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "commit", "-q", "-m", "add bug for t_bug7"], check=True)

    r_before = subprocess.run(["git", "-C", GIT_REPO, "rev-list", "--count", "HEAD"],
                               capture_output=True, text=True)
    commits_before = int(r_before.stdout.strip())

    t_bug7_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG7_DIR, "refused",
         "--reason", "wontfix", "--skip-vet-reason", "bypass"],
        capture_output=True
    ).returncode

    r_after = subprocess.run(["git", "-C", GIT_REPO, "rev-list", "--count", "HEAD"],
                              capture_output=True, text=True)
    commits_after = int(r_after.stdout.strip() or "0")

    if t_bug7_exit != 0:
        assert_fail(T_BUG7_LABEL, f"bug-status.sh set exited {t_bug7_exit} (transition failed; cannot check git commit)")
    elif commits_after > commits_before:
        assert_pass(T_BUG7_LABEL)
    else:
        assert_fail(T_BUG7_LABEL,
                    f"no new git commit after set transition (commits before={commits_before}, after={commits_after})")

    # ---------------------------------------------------------------------------
    # t_bug8: git commit created after file-bug.py creates a bug
    # ---------------------------------------------------------------------------
    T_BUG8_LABEL = "t_bug8: git commit created after file-bug.sh creates a bug"

    bugs_dir_git = os.path.join(GIT_REPO, ".claude/bugs/test-feature")
    os.makedirs(bugs_dir_git, exist_ok=True)

    r_before_file = subprocess.run(["git", "-C", GIT_REPO, "rev-list", "--count", "HEAD"],
                                    capture_output=True, text=True)
    commits_before_file = int(r_before_file.stdout.strip())

    t_bug8_exit = subprocess.run(
        [sys.executable, file_bug,
         "--title", "T", "--severity", "low", "--description", "D",
         "--related-feature", "test-feature"],
        cwd=GIT_REPO,
        capture_output=True
    ).returncode

    r_after_file = subprocess.run(["git", "-C", GIT_REPO, "rev-list", "--count", "HEAD"],
                                   capture_output=True, text=True)
    commits_after_file = int(r_after_file.stdout.strip() or "0")

    if t_bug8_exit != 0:
        assert_fail(T_BUG8_LABEL, f"file-bug.sh exited {t_bug8_exit} (filing failed; cannot check git commit)")
    elif commits_after_file > commits_before_file:
        assert_pass(T_BUG8_LABEL)
    else:
        assert_fail(T_BUG8_LABEL,
                    f"no new git commit after file-bug.sh (commits before={commits_before_file}, after={commits_after_file})")

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
