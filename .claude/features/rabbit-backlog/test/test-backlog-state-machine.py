#!/usr/bin/env python3
# test-backlog-state-machine.py — tests for the new state machine.
#
# State machine being tested:
#   open        -> in-progress   (--reason required)
#   open        -> refused       (--reason required)
#   in-progress -> implemented   (--reason required, --fix-commits required)
#   in-progress -> refused       (--reason required)
#   implemented -> reopened      (--reason required)
#   refused     -> reopened      (--reason required)
#   reopened    -> in-progress   (--reason required)
#   reopened    -> refused       (--reason required)
#
# Invalid/removed: done, cancelled
# Removed transition: open -> done (was valid before)

import subprocess
import sys
import json
import os
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(subprocess.check_output(
    ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
    text=True
).strip())
FEATURE_DIR = REPO_ROOT / ".claude" / "features" / "rabbit-backlog"
SCRIPTS_DIR = FEATURE_DIR / "scripts"
ITEM_STATUS = SCRIPTS_DIR / "backlog-item-status.py"

passed = 0
failed = 0


def ok(label):
    global passed
    print(f"  PASS  {label}")
    passed += 1


def fail_t(label, detail=""):
    global failed
    msg = f"  FAIL  {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    failed += 1


print("=== test-backlog-state-machine.py: new state machine ===")
print()

tmpdirs = []


def make_item_dir(status="open", name="DUMMY"):
    tmpdir = Path(tempfile.mkdtemp())
    tmpdirs.append(tmpdir)
    (tmpdir / "item.json").write_text(json.dumps({
        "name": name,
        "title": "test item",
        "status": status,
        "priority": "medium",
        "description": "",
        "owner": "test",
        "filed": "2026-05-11T00:00:00Z",
        "filed_by": "test",
        "closed": None,
        "history": [
            {"ts": "2026-05-11T00:00:00Z", "actor": "test", "action": "opened", "note": "initial filing"}
        ]
    }, indent=2))
    return tmpdir


def run_status(*args, capture=True):
    return subprocess.run(
        [sys.executable, str(ITEM_STATUS)] + list(args),
        capture_output=capture,
        text=True
    )


try:
    # t_new1: `implemented` is a valid status (in-progress -> implemented with --fix-commits)
    T = "t_new1: implemented is a valid status (in-progress -> implemented with --fix-commits)"
    d = make_item_dir("in-progress", "DUMMY-T1")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "implemented", "--reason", "shipped", "--fix-commits", "abc1234")
        if result.returncode == 0:
            status_val = json.loads((d / "item.json").read_text()).get("status")
            if status_val == "implemented":
                ok(T)
            else:
                fail_t(T, f"status in item.json is '{status_val}', expected 'implemented'")
        else:
            fail_t(T, "command exited non-zero")
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new2: `refused` is a valid status (open -> refused with --reason)
    T = "t_new2: refused is a valid status (open -> refused with --reason)"
    d = make_item_dir("open", "DUMMY-T2")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "refused", "--reason", "not a real feature")
        if result.returncode == 0:
            status_val = json.loads((d / "item.json").read_text()).get("status")
            if status_val == "refused":
                ok(T)
            else:
                fail_t(T, f"status in item.json is '{status_val}', expected 'refused'")
        else:
            fail_t(T, "command exited non-zero")
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new3: `reopened` is a valid status (implemented -> reopened with --reason)
    T = "t_new3: reopened is a valid status (implemented -> reopened with --reason)"
    d = make_item_dir("implemented", "DUMMY-T3")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "reopened", "--reason", "regression found")
        if result.returncode == 0:
            status_val = json.loads((d / "item.json").read_text()).get("status")
            if status_val == "reopened":
                ok(T)
            else:
                fail_t(T, f"status in item.json is '{status_val}', expected 'reopened'")
        else:
            fail_t(T, "command exited non-zero on valid implemented->reopened transition")
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new4: `done` is NOT a valid status (rejected)
    T = "t_new4: done is NOT a valid status (rejected)"
    d = make_item_dir("open", "DUMMY-T4")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "done", "--reason", "done")
        if result.returncode == 0:
            fail_t(T, "command succeeded but 'done' should be rejected as invalid status")
        else:
            ok(T)
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new5: `cancelled` is NOT a valid status (rejected)
    T = "t_new5: cancelled is NOT a valid status (rejected)"
    d = make_item_dir("open", "DUMMY-T5")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "cancelled", "--reason", "cancelling")
        if result.returncode == 0:
            fail_t(T, "command succeeded but 'cancelled' should be rejected as invalid status")
        else:
            ok(T)
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new6: --reason is required on every set (omitting exits non-zero)
    T = "t_new6: --reason is required on every set (omitting exits non-zero)"
    d = make_item_dir("open", "DUMMY-T6")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "in-progress")
        if result.returncode == 0:
            fail_t(T, "command succeeded without --reason but should require it")
        else:
            ok(T)
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new7: --fix-commits required when transitioning to implemented (missing exits non-zero)
    T = "t_new7: --fix-commits required when transitioning to implemented (missing exits non-zero)"
    d = make_item_dir("in-progress", "DUMMY-T7")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "implemented", "--reason", "shipped")
        if result.returncode == 0:
            fail_t(T, "command succeeded without --fix-commits but should require it for 'implemented'")
        else:
            ok(T)
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new8: --fix-commits is rejected for non-implemented transitions (open -> in-progress)
    T = "t_new8: --fix-commits rejected on non-implemented transitions (open -> in-progress)"
    d = make_item_dir("open", "DUMMY-T8")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "in-progress", "--reason", "starting", "--fix-commits", "abc1234")
        if result.returncode == 0:
            fail_t(T, "command succeeded with --fix-commits on a non-implemented transition but should reject it")
        else:
            ok(T)
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new9: implemented -> reopened is a valid transition
    T = "t_new9: implemented -> reopened is a valid transition"
    d = make_item_dir("implemented", "DUMMY-T9")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "reopened", "--reason", "found regression")
        if result.returncode == 0:
            status_val = json.loads((d / "item.json").read_text()).get("status")
            if status_val == "reopened":
                ok(T)
            else:
                fail_t(T, f"status in item.json is '{status_val}', expected 'reopened'")
        else:
            fail_t(T, "command exited non-zero on valid implemented->reopened transition")
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new10: refused -> reopened is a valid transition
    T = "t_new10: refused -> reopened is a valid transition"
    d = make_item_dir("refused", "DUMMY-T10")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "reopened", "--reason", "reconsidered")
        if result.returncode == 0:
            status_val = json.loads((d / "item.json").read_text()).get("status")
            if status_val == "reopened":
                ok(T)
            else:
                fail_t(T, f"status in item.json is '{status_val}', expected 'reopened'")
        else:
            fail_t(T, "command exited non-zero on valid refused->reopened transition")
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new11: reopened -> in-progress is a valid transition
    T = "t_new11: reopened -> in-progress is a valid transition"
    d = make_item_dir("reopened", "DUMMY-T11")
    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(d), "in-progress", "--reason", "resuming work")
        if result.returncode == 0:
            status_val = json.loads((d / "item.json").read_text()).get("status")
            if status_val == "in-progress":
                ok(T)
            else:
                fail_t(T, f"status in item.json is '{status_val}', expected 'in-progress'")
        else:
            fail_t(T, "command exited non-zero on valid reopened->in-progress transition")
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

    # t_new12: a git commit is created after a successful set transition
    T = "t_new12: a git commit is created after a successful set transition"
    GIT_TMPDIR = Path(tempfile.mkdtemp())
    tmpdirs.append(GIT_TMPDIR)
    ITEM_SUBDIR = GIT_TMPDIR / "item"
    ITEM_SUBDIR.mkdir()

    subprocess.run(["git", "-C", str(GIT_TMPDIR), "init", "-q"], capture_output=True)
    subprocess.run(["git", "-C", str(GIT_TMPDIR), "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "-C", str(GIT_TMPDIR), "config", "user.name", "Test"], check=True)

    (ITEM_SUBDIR / "item.json").write_text(json.dumps({
        "name": "DUMMY-T12",
        "title": "t12 item",
        "status": "open",
        "priority": "medium",
        "description": "",
        "owner": "test",
        "filed": "2026-05-11T00:00:00Z",
        "filed_by": "test",
        "closed": None,
        "history": [
            {"ts": "2026-05-11T00:00:00Z", "actor": "test", "action": "opened", "note": "initial filing"}
        ]
    }, indent=2))

    subprocess.run(["git", "-C", str(GIT_TMPDIR), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(GIT_TMPDIR), "commit", "-qm", "initial"], capture_output=True)

    commit_before = subprocess.check_output(
        ["git", "-C", str(GIT_TMPDIR), "rev-parse", "HEAD"],
        text=True
    ).strip()

    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = run_status("set", str(ITEM_SUBDIR), "in-progress", "--reason", "starting")
        if result.returncode == 0:
            commit_after = subprocess.check_output(
                ["git", "-C", str(GIT_TMPDIR), "rev-parse", "HEAD"],
                text=True
            ).strip()
            if commit_before != commit_after:
                ok(T)
            else:
                fail_t(T, "HEAD did not advance after set (no commit was created)")
        else:
            fail_t(T, "set in-progress --reason starting exited non-zero")
    else:
        fail_t(T, "backlog-item-status.py not found or not executable")

finally:
    for d in tmpdirs:
        shutil.rmtree(d, ignore_errors=True)

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
