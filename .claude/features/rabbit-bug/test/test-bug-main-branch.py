#!/usr/bin/env python3
# test-bug-main-branch.py
# Tests for main-branch guard in file-bug.py and user-decision gate in SKILL.md.
#
# t_mb1: file-bug.py exits non-zero when current branch is not main (no tty, non-interactive)
# t_mb2: file-bug.py succeeds when current branch is main
# t_mb3: file-bug.py prints a warning to stderr when not on main branch
# t_mb4: SKILL.md Working Protocol contains user-decision gate language (brief + ask before dispatch)
#
# Exit: 1 if any assertion fails.

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(FEATURE_DIR, "scripts")
SKILL_MD = os.path.join(FEATURE_DIR, "skills/rabbit-bug/SKILL.md")

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
    # Setup: create a temp git repo with a feature for filing bugs
    # ---------------------------------------------------------------------------
    GIT_REPO = os.path.join(TMPDIR_ROOT, "test-repo")
    os.makedirs(GIT_REPO)
    subprocess.run(["git", "-C", GIT_REPO, "init", "-q"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "config", "user.name", "Test User"], check=True)

    # Make an initial commit on main
    readme = os.path.join(GIT_REPO, "README")
    open(readme, "w").close()
    subprocess.run(["git", "-C", GIT_REPO, "add", "README"], check=True)
    subprocess.run(["git", "-C", GIT_REPO, "commit", "-q", "-m", "init"], check=True)

    # Ensure default branch is named 'main'
    r = subprocess.run(["git", "-C", GIT_REPO, "branch", "--show-current"],
                       capture_output=True, text=True)
    current_branch = r.stdout.strip()
    if current_branch != "main":
        subprocess.run(["git", "-C", GIT_REPO, "branch", "-m", current_branch, "main"],
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
            "summary": "Test feature for main-branch tests."
        }, f)

    # Create a non-main branch
    subprocess.run(["git", "-C", GIT_REPO, "checkout", "-q", "-b", "feature/some-work"],
                   check=False, capture_output=True)

    file_bug = os.path.join(SCRIPTS_DIR, "file-bug.py")

    # ---------------------------------------------------------------------------
    # t_mb1: file-bug.py exits non-zero when current branch is not main
    # ---------------------------------------------------------------------------
    T_MB1_LABEL = "t_mb1: file-bug.sh exits non-zero when not on main branch"

    t_mb1_result = subprocess.run(
        [sys.executable, file_bug,
         "--title", "T", "--severity", "low", "--description", "D",
         "--related-feature", "test-feature"],
        cwd=GIT_REPO,
        stdin=subprocess.DEVNULL,
        capture_output=True
    )
    t_mb1_exit = t_mb1_result.returncode

    if t_mb1_exit != 0:
        assert_pass(T_MB1_LABEL)
    else:
        assert_fail(T_MB1_LABEL, "file-bug.sh exited 0 on non-main branch (expected non-zero)")

    # ---------------------------------------------------------------------------
    # t_mb2: file-bug.py succeeds when current branch is main
    # ---------------------------------------------------------------------------
    T_MB2_LABEL = "t_mb2: file-bug.sh succeeds when current branch is main"

    subprocess.run(["git", "-C", GIT_REPO, "checkout", "-q", "main"],
                   check=False, capture_output=True)

    t_mb2_exit = subprocess.run(
        [sys.executable, file_bug,
         "--title", "T", "--severity", "low", "--description", "D",
         "--related-feature", "test-feature"],
        cwd=GIT_REPO,
        capture_output=True
    ).returncode

    if t_mb2_exit == 0:
        assert_pass(T_MB2_LABEL)
    else:
        assert_fail(T_MB2_LABEL, f"file-bug.sh exited {t_mb2_exit} on main branch (expected 0)")

    # Switch back to non-main for remaining tests
    subprocess.run(["git", "-C", GIT_REPO, "checkout", "-q", "feature/some-work"],
                   check=False, capture_output=True)

    # ---------------------------------------------------------------------------
    # t_mb3: file-bug.py prints a warning to stderr when not on main branch
    # ---------------------------------------------------------------------------
    T_MB3_LABEL = "t_mb3: file-bug.sh prints warning to stderr when not on main branch"

    t_mb3_result = subprocess.run(
        [sys.executable, file_bug,
         "--title", "T", "--severity", "low", "--description", "D",
         "--related-feature", "test-feature"],
        cwd=GIT_REPO,
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True
    )
    stderr_content = t_mb3_result.stderr

    if re.search(r'warn|not.*main|main.*branch|branch.*main', stderr_content, re.IGNORECASE):
        assert_pass(T_MB3_LABEL)
    else:
        assert_fail(T_MB3_LABEL, f"no branch warning found in stderr: '{stderr_content}'")

    # ---------------------------------------------------------------------------
    # t_mb4: SKILL.md Working Protocol contains user-decision gate language
    # ---------------------------------------------------------------------------
    T_MB4_LABEL = "t_mb4: SKILL.md Working Protocol has user-decision gate (brief + ask before dispatch)"

    if not os.path.isfile(SKILL_MD):
        assert_fail(T_MB4_LABEL, f"SKILL.md not found at {SKILL_MD}")
    else:
        content = open(SKILL_MD).read()
        has_brief = bool(re.search(
            r'brief|summary|recommendation|eval.*summary|eval.*finding|summarize',
            content, re.IGNORECASE
        ))
        has_ask = bool(re.search(
            r'ask|confirm|whether.*refuse|whether.*work|before.*dispatch|before.*rabbit-feature-touch|user.*decide|decision',
            content, re.IGNORECASE
        ))
        if has_brief and has_ask:
            assert_pass(T_MB4_LABEL)
        else:
            assert_fail(T_MB4_LABEL,
                        f"missing gate language — HAS_BRIEF={int(has_brief)} HAS_ASK={int(has_ask)} (both must be 1)")

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
