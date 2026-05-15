#!/usr/bin/env python3
# test-bug-git-isolation.py
# Regression tests for RABBIT-BUG-4: tests use ISO_REPO to keep live repo clean.
#
# t_iso1: file-bug.py run from ISO_REPO does NOT commit to the live repo,
#         AND DOES commit to ISO_REPO (audit trail works).
# t_iso2: bug-status.py run from ISO_REPO does NOT commit to the live repo,
#         AND DOES commit to ISO_REPO (audit trail works).
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

r = subprocess.run(["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
                   capture_output=True, text=True)
REPO_ROOT = r.stdout.strip()

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


ISO_REPO = tempfile.mkdtemp()
try:
    # ---------------------------------------------------------------------------
    # ISO_REPO setup: a fresh git repo separate from the live repo.
    # ---------------------------------------------------------------------------
    subprocess.run(["git", "-C", ISO_REPO, "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", ISO_REPO, "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", ISO_REPO, "config", "user.name", "rabbit-test"], check=True)
    subprocess.run(["git", "-C", ISO_REPO, "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)

    # Ensure branch is 'main'
    r2 = subprocess.run(["git", "-C", ISO_REPO, "branch", "--show-current"],
                        capture_output=True, text=True)
    init_branch = r2.stdout.strip()
    if init_branch != "main":
        subprocess.run(["git", "-C", ISO_REPO, "branch", "-m", init_branch, "main"],
                       check=False, capture_output=True)

    # Install find-feature.py in ISO_REPO
    rabbit_root = os.environ.get("RABBIT_ROOT")
    if not rabbit_root:
        r3 = subprocess.run(["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True)
        rabbit_root = r3.stdout.strip()

    find_feature_src = os.path.join(rabbit_root, ".claude/features/contract/scripts/find-feature.py")
    find_feature_dst_dir = os.path.join(ISO_REPO, ".claude/features/contract/scripts")
    os.makedirs(find_feature_dst_dir, exist_ok=True)
    find_feature_dst = os.path.join(find_feature_dst_dir, "find-feature.py")
    shutil.copy(find_feature_src, find_feature_dst)
    os.chmod(find_feature_dst, 0o755)

    # Create feature.json for test-feature
    test_feature_dir = os.path.join(ISO_REPO, ".claude/features/test-feature")
    os.makedirs(test_feature_dir, exist_ok=True)
    with open(os.path.join(test_feature_dir, "feature.json"), "w") as f:
        json.dump({"name": "test-feature", "owner": "tester", "version": "1.0"}, f)

    file_bug = os.path.join(SCRIPTS_DIR, "file-bug.py")
    bug_status = os.path.join(SCRIPTS_DIR, "bug-status.py")

    # ---------------------------------------------------------------------------
    # t_iso1: file-bug.py run from ISO_REPO
    # ---------------------------------------------------------------------------
    T_ISO1_LABEL = "t_iso1: file-bug.sh (ISO_REPO) keeps live repo clean AND commits in ISO_REPO"

    r_live_before = subprocess.run(["git", "-C", REPO_ROOT, "rev-list", "--count", "HEAD"],
                                   capture_output=True, text=True)
    live_before = int(r_live_before.stdout.strip())

    r_iso_before = subprocess.run(["git", "-C", ISO_REPO, "rev-list", "--count", "HEAD"],
                                  capture_output=True, text=True)
    iso_before = int(r_iso_before.stdout.strip())

    file_exit = subprocess.run(
        [sys.executable, file_bug,
         "--title", "Isolation Probe", "--severity", "low",
         "--description", "ISO_REPO isolation test",
         "--related-feature", "test-feature"],
        cwd=ISO_REPO,
        capture_output=True
    ).returncode

    r_live_after = subprocess.run(["git", "-C", REPO_ROOT, "rev-list", "--count", "HEAD"],
                                  capture_output=True, text=True)
    live_after = int(r_live_after.stdout.strip())

    r_iso_after = subprocess.run(["git", "-C", ISO_REPO, "rev-list", "--count", "HEAD"],
                                 capture_output=True, text=True)
    iso_after = int(r_iso_after.stdout.strip())

    if file_exit != 0:
        assert_fail(T_ISO1_LABEL, f"file-bug.sh exited {file_exit}; cannot confirm isolation")
    elif live_after > live_before:
        assert_fail(T_ISO1_LABEL,
                    f"live repo gained commit(s): before={live_before} after={live_after} — script polluted live repo")
    elif iso_after <= iso_before:
        assert_fail(T_ISO1_LABEL,
                    f"ISO_REPO commit count did not increase: before={iso_before} after={iso_after} — audit trail broken")
    else:
        assert_pass(T_ISO1_LABEL)

    # ---------------------------------------------------------------------------
    # t_iso2: bug-status.py run from ISO_REPO
    # ---------------------------------------------------------------------------
    T_ISO2_LABEL = "t_iso2: bug-status.sh (ISO_REPO) keeps live repo clean AND commits in ISO_REPO"

    # Create a bug.json in ISO_REPO to transition
    BUG_DIR = os.path.join(ISO_REPO, ".claude/bugs/test-feature/TEST-FEATURE-ISO2")
    os.makedirs(BUG_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bug_data = {
        "name": "TEST-FEATURE-ISO2",
        "title": "ISO2 Test",
        "status": "open",
        "severity": "low",
        "description": "isolation test",
        "related_feature": "test-feature",
        "filed": ts,
        "filed_by": "tester",
        "closed": None,
        "closed_by": None,
        "history": [{"ts": ts, "actor": "tester", "action": "opened", "note": "initial filing"}]
    }
    with open(os.path.join(BUG_DIR, "bug.json"), "w") as f:
        json.dump(bug_data, f)

    r_live_before2 = subprocess.run(["git", "-C", REPO_ROOT, "rev-list", "--count", "HEAD"],
                                    capture_output=True, text=True)
    live_before2 = int(r_live_before2.stdout.strip())

    r_iso_before2 = subprocess.run(["git", "-C", ISO_REPO, "rev-list", "--count", "HEAD"],
                                   capture_output=True, text=True)
    iso_before2 = int(r_iso_before2.stdout.strip())

    set_exit = subprocess.run(
        [sys.executable, bug_status, "set", BUG_DIR, "refused",
         "--reason", "isolation probe", "--skip-vet-reason", "test"],
        cwd=ISO_REPO,
        capture_output=True
    ).returncode

    r_live_after2 = subprocess.run(["git", "-C", REPO_ROOT, "rev-list", "--count", "HEAD"],
                                   capture_output=True, text=True)
    live_after2 = int(r_live_after2.stdout.strip())

    r_iso_after2 = subprocess.run(["git", "-C", ISO_REPO, "rev-list", "--count", "HEAD"],
                                  capture_output=True, text=True)
    iso_after2 = int(r_iso_after2.stdout.strip())

    if set_exit != 0:
        assert_fail(T_ISO2_LABEL, f"bug-status.sh set exited {set_exit}; cannot confirm isolation")
    elif live_after2 > live_before2:
        assert_fail(T_ISO2_LABEL,
                    f"live repo gained commit(s): before={live_before2} after={live_after2} — script polluted live repo")
    elif iso_after2 <= iso_before2:
        assert_fail(T_ISO2_LABEL,
                    f"ISO_REPO commit count did not increase: before={iso_before2} after={iso_after2} — audit trail broken")
    else:
        assert_pass(T_ISO2_LABEL)

finally:
    shutil.rmtree(ISO_REPO, ignore_errors=True)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("")
print(f"Results: {passed} passed, {failed} failed")

if failed > 0:
    sys.exit(1)
sys.exit(0)
