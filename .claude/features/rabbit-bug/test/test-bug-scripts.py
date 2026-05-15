#!/usr/bin/env python3
# test-bug-scripts.py
# Tests t1–t11 for the rabbit-bug feature — centralized storage design.
#
# t1:  scripts/file-bug.py exists and is executable
# t2:  scripts/bug-status.py exists and is executable
# t3:  scripts/list-bugs.py exists and is executable
# t4:  file-bug.py --related-feature test-feature writes to isolated repo's .claude/bugs/test-feature/TEST-FEATURE-1/bug.json
# t5:  bug.json has status=open, first history entry action=opened, name=TEST-FEATURE-1
# t6:  file-bug.py --related-feature nonexistent-feature-xyz fails with non-zero exit (registry validation)
# t7:  bug-status.py set BUG_DIR closed --reason r --skip-vet-reason s --fix-commits abc --touched-files f.sh
#        stores fix_commits and touched_files in history entry
# t8:  description field is unchanged after status transition
# t9:  list-bugs.py --feature test-feature --text returns the bug created in t4 (scans centralized path)
# t10: feature.json does NOT contain bugs_root key
# t11: list-bugs.py --text output includes severity in [SEVERITY] format
#
# Exit: 1 if any assertion fails.

import json
import os
import shutil
import subprocess
import sys
import tempfile

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


# ---------------------------------------------------------------------------
# t1: file-bug.py exists and is executable
# ---------------------------------------------------------------------------
T1_LABEL = "t1: scripts/file-bug.py exists and is executable"
file_bug = os.path.join(SCRIPTS_DIR, "file-bug.py")
if os.path.isfile(file_bug) and os.access(file_bug, os.X_OK):
    assert_pass(T1_LABEL)
else:
    assert_fail(T1_LABEL, f"file-bug.py missing or not executable at {file_bug}")

# ---------------------------------------------------------------------------
# t2: bug-status.py exists and is executable
# ---------------------------------------------------------------------------
T2_LABEL = "t2: scripts/bug-status.py exists and is executable"
bug_status = os.path.join(SCRIPTS_DIR, "bug-status.py")
if os.path.isfile(bug_status) and os.access(bug_status, os.X_OK):
    assert_pass(T2_LABEL)
else:
    assert_fail(T2_LABEL, f"bug-status.py missing or not executable at {bug_status}")

# ---------------------------------------------------------------------------
# t3: list-bugs.py exists and is executable
# ---------------------------------------------------------------------------
T3_LABEL = "t3: scripts/list-bugs.py exists and is executable"
list_bugs = os.path.join(SCRIPTS_DIR, "list-bugs.py")
if os.path.isfile(list_bugs) and os.access(list_bugs, os.X_OK):
    assert_pass(T3_LABEL)
else:
    assert_fail(T3_LABEL, f"list-bugs.py missing or not executable at {list_bugs}")

# ---------------------------------------------------------------------------
# t4–t11 require file-bug.py; report FAIL for all if missing
# ---------------------------------------------------------------------------
if not os.access(file_bug, os.X_OK):
    for t in ["t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11"]:
        assert_fail(t, "file-bug.py not executable — cannot run")
    print("")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Isolated git repo setup for t4–t11
# ---------------------------------------------------------------------------
ISO_REPO = tempfile.mkdtemp()
try:
    subprocess.run(["git", "-C", ISO_REPO, "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", ISO_REPO, "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", ISO_REPO, "config", "user.name", "rabbit-test"], check=True)
    subprocess.run(["git", "-C", ISO_REPO, "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)

    # Ensure branch is 'main'
    result = subprocess.run(
        ["git", "-C", ISO_REPO, "branch", "--show-current"],
        capture_output=True, text=True
    )
    init_branch = result.stdout.strip()
    if init_branch != "main":
        subprocess.run(["git", "-C", ISO_REPO, "branch", "-m", init_branch, "main"],
                       check=False, capture_output=True)

    # Install find-feature.py in ISO_REPO
    rabbit_root = os.environ.get("RABBIT_ROOT")
    if not rabbit_root:
        r = subprocess.run(
            ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        rabbit_root = r.stdout.strip()

    find_feature_src = os.path.join(rabbit_root, ".claude/features/contract/scripts/find-feature.py")
    find_feature_dst_dir = os.path.join(ISO_REPO, ".claude/features/contract/scripts")
    os.makedirs(find_feature_dst_dir, exist_ok=True)
    find_feature_dst = os.path.join(find_feature_dst_dir, "find-feature.py")
    shutil.copy(find_feature_src, find_feature_dst)
    os.chmod(find_feature_dst, 0o755)

    # Create feature.json for test-feature
    test_feature_dir = os.path.join(ISO_REPO, ".claude/features/test-feature")
    os.makedirs(test_feature_dir, exist_ok=True)
    feature_json_content = {
        "name": "test-feature",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "Test feature for bug filing tests."
    }
    with open(os.path.join(test_feature_dir, "feature.json"), "w") as f:
        json.dump(feature_json_content, f)

    # ---------------------------------------------------------------------------
    # t4: file-bug.py --related-feature test-feature creates .claude/bugs/test-feature/TEST-FEATURE-1/bug.json
    # ---------------------------------------------------------------------------
    T4_LABEL = "t4: file-bug.sh --related-feature test-feature creates .claude/bugs/test-feature/TEST-FEATURE-1/bug.json"
    EXPECTED_BUG_JSON = os.path.join(ISO_REPO, ".claude/bugs/test-feature/TEST-FEATURE-1/bug.json")

    file_exit = subprocess.run(
        [sys.executable, file_bug,
         "--title", "T", "--severity", "low", "--description", "D",
         "--related-feature", "test-feature"],
        cwd=ISO_REPO,
        capture_output=True
    ).returncode

    if file_exit != 0:
        assert_fail(T4_LABEL, f"file-bug.py exited with code {file_exit} (expected 0)")
    elif not os.path.isfile(EXPECTED_BUG_JSON):
        assert_fail(T4_LABEL, f"expected bug.json not found at {EXPECTED_BUG_JSON}")
    else:
        assert_pass(T4_LABEL)

    BUG_JSON = EXPECTED_BUG_JSON

    # ---------------------------------------------------------------------------
    # t5: bug.json has status=open, first history entry action=opened, name=TEST-FEATURE-1
    # ---------------------------------------------------------------------------
    T5_LABEL = "t5: bug.json status=open, first history entry action=opened, name=TEST-FEATURE-1"

    if not os.path.isfile(BUG_JSON):
        assert_fail(T5_LABEL, "no bug.json available (t4 failed)")
    else:
        with open(BUG_JSON) as f:
            bug_data = json.load(f)
        status = bug_data.get("status", "")
        first_action = bug_data.get("history", [{}])[0].get("action", "") if bug_data.get("history") else ""
        name_val = bug_data.get("name", "")
        if status == "open" and first_action == "opened" and name_val == "TEST-FEATURE-1":
            assert_pass(T5_LABEL)
        else:
            assert_fail(T5_LABEL,
                        f"status={status} (want open), first history action={first_action} (want opened), name={name_val} (want TEST-FEATURE-1)")

    # ---------------------------------------------------------------------------
    # t6: file-bug.py --related-feature nonexistent-feature-xyz fails (registry validation)
    # ---------------------------------------------------------------------------
    T6_LABEL = "t6: file-bug.sh --related-feature nonexistent-feature-xyz fails with non-zero exit"

    t6_exit = subprocess.run(
        [sys.executable, file_bug,
         "--title", "T", "--severity", "low", "--description", "D",
         "--related-feature", "nonexistent-feature-xyz"],
        cwd=ISO_REPO,
        capture_output=True
    ).returncode

    if t6_exit != 0:
        assert_pass(T6_LABEL)
    else:
        assert_fail(T6_LABEL, "file-bug.py exited 0 for unknown feature (expected non-zero)")

    # ---------------------------------------------------------------------------
    # t7: bug-status.py set BUG_DIR closed --fix-commits abc --touched-files f.sh
    # ---------------------------------------------------------------------------
    T7_LABEL = "t7: bug-status.sh set closed --fix-commits abc --touched-files f.sh stores those fields in history"

    BUG_DIR = os.path.dirname(BUG_JSON) if os.path.isfile(BUG_JSON) else "/nonexistent"

    if not os.access(bug_status, os.X_OK) or not os.path.isfile(BUG_JSON):
        assert_fail(T7_LABEL, "bug-status.py not executable or no bug.json")
    else:
        set7_exit = subprocess.run(
            [sys.executable, bug_status, "set", BUG_DIR, "closed",
             "--reason", "r", "--skip-vet-reason", "s",
             "--fix-commits", "abc", "--touched-files", "f.sh"],
            capture_output=True
        ).returncode

        if set7_exit != 0:
            assert_fail(T7_LABEL, f"bug-status.py exited with code {set7_exit}")
        else:
            with open(BUG_JSON) as f:
                bug_data7 = json.load(f)
            closed_entries = [h for h in bug_data7.get("history", []) if h.get("action") == "closed"]
            last_closed = closed_entries[-1] if closed_entries else {}
            fix_commits = last_closed.get("fix_commits", "")
            touched_files = last_closed.get("touched_files", "")
            if fix_commits and touched_files:
                assert_pass(T7_LABEL)
            else:
                assert_fail(T7_LABEL,
                            f"fix_commits='{fix_commits}' touched_files='{touched_files}' (both must be non-empty)")

    # ---------------------------------------------------------------------------
    # t8: description field unchanged after status transitions
    # ---------------------------------------------------------------------------
    T8_LABEL = "t8: description field unchanged after status transitions"

    if not os.path.isfile(BUG_JSON):
        assert_fail(T8_LABEL, "no bug.json available")
    else:
        with open(BUG_JSON) as f:
            bug_data8 = json.load(f)
        desc_now = bug_data8.get("description", "")
        if desc_now == "D":
            assert_pass(T8_LABEL)
        else:
            assert_fail(T8_LABEL, f"description changed: got '{desc_now}' (want 'D')")

    # ---------------------------------------------------------------------------
    # t9: list-bugs.py --feature test-feature --text returns bug created in t4
    # ---------------------------------------------------------------------------
    T9_LABEL = "t9: list-bugs.sh --feature test-feature --text returns bug created in t4"

    if not os.access(list_bugs, os.X_OK) or not os.path.isfile(BUG_JSON):
        assert_fail(T9_LABEL, "list-bugs.py not executable or no bug.json")
    else:
        with open(BUG_JSON) as f:
            bug_data9 = json.load(f)
        bug_name = bug_data9.get("name", "")
        t9_result = subprocess.run(
            [sys.executable, list_bugs, "--feature", "test-feature", "--text"],
            cwd=ISO_REPO,
            capture_output=True, text=True
        )
        list_exit = t9_result.returncode
        text_out = t9_result.stdout + t9_result.stderr
        if list_exit != 0:
            assert_fail(T9_LABEL, f"list-bugs.py exited with code {list_exit}")
        elif bug_name in text_out:
            assert_pass(T9_LABEL)
        else:
            assert_fail(T9_LABEL,
                        f"bug name '{bug_name}' not found in --text output: {text_out[:300]}")

    # ---------------------------------------------------------------------------
    # t11: list-bugs.py --text output includes [SEVERITY] field
    # ---------------------------------------------------------------------------
    T11_LABEL = "t11: list-bugs.sh --text output includes [SEVERITY] field"

    if not os.access(list_bugs, os.X_OK) or not os.path.isfile(BUG_JSON):
        assert_fail(T11_LABEL, "list-bugs.py not executable or no bug.json")
    else:
        with open(BUG_JSON) as f:
            bug_data11 = json.load(f)
        severity_val = bug_data11.get("severity", "")
        t11_result = subprocess.run(
            [sys.executable, list_bugs, "--feature", "test-feature", "--text"],
            cwd=ISO_REPO,
            capture_output=True, text=True
        )
        list11_exit = t11_result.returncode
        text_out11 = t11_result.stdout + t11_result.stderr
        if list11_exit != 0:
            assert_fail(T11_LABEL, f"list-bugs.py exited with code {list11_exit}")
        elif f"[{severity_val}]" in text_out11:
            assert_pass(T11_LABEL)
        else:
            assert_fail(T11_LABEL,
                        f"severity '[{severity_val}]' not found in --text output: {text_out11[:300]}")

    # ---------------------------------------------------------------------------
    # t10: feature.json does NOT contain bugs_root key
    # ---------------------------------------------------------------------------
    T10_LABEL = "t10: feature.json does NOT contain bugs_root key"

    feat_json = os.path.join(FEATURE_DIR, "feature.json")
    if not os.path.isfile(feat_json):
        assert_fail(T10_LABEL, f"feature.json not found at {feat_json}")
    else:
        with open(feat_json) as f:
            feat_data = json.load(f)
        bugs_root_val = feat_data.get("bugs_root", "ABSENT")
        if bugs_root_val == "ABSENT" or bugs_root_val is None:
            assert_pass(T10_LABEL)
        else:
            assert_fail(T10_LABEL, f"bugs_root is still present in feature.json: '{bugs_root_val}'")

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
