#!/usr/bin/env python3
# test-tdd-report-gate.py — verify --tdd-report flag and updated R7 gate

import json
import os
import subprocess
import sys
import tempfile

r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
REPO_ROOT = r.stdout.strip()

SCRIPT = os.path.join(REPO_ROOT, ".claude/features/rabbit-bug/scripts/bug-status.py")

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


TMPDIR_TEST = tempfile.mkdtemp()
BUG_DIR = os.path.join(TMPDIR_TEST, "RABBIT-BUG-99")
os.makedirs(BUG_DIR, exist_ok=True)

try:
    def reset_bug():
        bug = {
            "id": "RABBIT-BUG-99",
            "title": "test bug",
            "severity": "low",
            "status": "open",
            "history": []
        }
        with open(os.path.join(BUG_DIR, "bug.json"), "w") as f:
            json.dump(bug, f)

    reset_bug()

    # 1. close fails without vet-triage.json (baseline R7 still works)
    code = subprocess.run(
        [sys.executable, SCRIPT, "set", BUG_DIR, "closed", "--reason", "fix"],
        capture_output=True
    ).returncode
    if code != 0:
        ok("close fails without vet-triage.json")
    else:
        fail("should fail without vet-triage.json")

    # 2. close fails with vet-triage.json but no --tdd-report
    open(os.path.join(BUG_DIR, "vet-triage.json"), "w").close()
    code = subprocess.run(
        [sys.executable, SCRIPT, "set", BUG_DIR, "closed", "--reason", "fix"],
        capture_output=True
    ).returncode
    if code != 0:
        ok("close fails without --tdd-report")
    else:
        fail("should fail without --tdd-report")

    # 3. close succeeds with vet-triage.json + --tdd-report
    tdd_report_path = os.path.join(TMPDIR_TEST, "tdd-report.json")
    tdd_report = {
        "schema_version": "1.0.0",
        "feature": "test",
        "test_result": "pass",
        "tdd_state": "test-green",
        "impl_summary": "fixed",
        "spec_compliance": "pass",
        "test_gap_analysis": "none",
        "impl_commit": "abc123"
    }
    with open(tdd_report_path, "w") as f:
        json.dump(tdd_report, f)

    code = subprocess.run(
        [sys.executable, SCRIPT, "set", BUG_DIR, "closed",
         "--reason", "TDD cycle complete",
         "--tdd-report", tdd_report_path,
         "--fix-commits", "abc123"],
        capture_output=True
    ).returncode
    if code == 0:
        ok("close succeeds with vet-triage.json + --tdd-report")
    else:
        fail(f"close failed: exit {code}")

    # 4. bug.json history contains tdd_report field
    with open(os.path.join(BUG_DIR, "bug.json")) as f:
        bug_data = json.load(f)
    h = bug_data.get("history", [])
    has_rpt = h and "tdd_report" in h[-1]
    if has_rpt:
        ok("bug.json history has tdd_report field")
    else:
        fail("bug.json missing tdd_report in history")

    # 5. tdd-gap.json is NOT required (old requirement removed)
    reset_bug()
    open(os.path.join(BUG_DIR, "vet-triage.json"), "w").close()
    tdd_gap = os.path.join(BUG_DIR, "tdd-gap.json")
    if os.path.isfile(tdd_gap):
        os.remove(tdd_gap)

    code = subprocess.run(
        [sys.executable, SCRIPT, "set", BUG_DIR, "closed",
         "--reason", "fix",
         "--tdd-report", tdd_report_path,
         "--fix-commits", "abc123"],
        capture_output=True
    ).returncode
    if code == 0:
        ok("tdd-gap.json not required")
    else:
        fail(f"should not require tdd-gap.json: exit {code}")

finally:
    import shutil
    shutil.rmtree(TMPDIR_TEST, ignore_errors=True)

print("")
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
