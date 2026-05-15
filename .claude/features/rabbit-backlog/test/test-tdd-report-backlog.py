#!/usr/bin/env python3
# test-tdd-report-backlog.py

import subprocess
import sys
import json
import tempfile
import shutil
from pathlib import Path

REPO_ROOT = Path(subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"],
    text=True
).strip())
SCRIPT = REPO_ROOT / ".claude" / "features" / "rabbit-backlog" / "scripts" / "backlog-item-status.py"

PASS = 0
FAIL = 0


def ok(label):
    global PASS
    print(f"PASS: {label}")
    PASS += 1


def fail(label):
    global FAIL
    print(f"FAIL: {label}")
    FAIL += 1


tmpdir = Path(tempfile.mkdtemp())
try:
    ITEM_DIR = tmpdir / "RABBIT-BACKLOG-99"
    ITEM_DIR.mkdir()

    (ITEM_DIR / "item.json").write_text(json.dumps({
        "id": "RABBIT-BACKLOG-99",
        "title": "test item",
        "priority": "medium",
        "status": "in-progress",
        "history": []
    }))
    (tmpdir / "tdd-report.json").write_text(json.dumps({
        "schema_version": "1.0.0",
        "feature": "test",
        "test_result": "pass",
        "tdd_state": "test-green",
        "impl_summary": "done",
        "spec_compliance": "pass",
        "test_gap_analysis": "none",
        "impl_commit": "abc123"
    }))

    # 1. implemented with --tdd-report succeeds
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "set", str(ITEM_DIR), "implemented",
         "--reason", "TDD complete",
         "--tdd-report", str(tmpdir / "tdd-report.json"),
         "--fix-commits", "abc123"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        ok("implemented with --tdd-report succeeds")
    else:
        fail(f"implemented failed: {result.returncode}")

    # 2. item.json history has tdd_report field
    h = json.loads((ITEM_DIR / "item.json").read_text()).get("history", [])
    if h and "tdd_report" in h[-1]:
        ok("history has tdd_report field")
    else:
        fail("missing tdd_report in history")

    # 3. item.json history has fix_commits field
    h = json.loads((ITEM_DIR / "item.json").read_text()).get("history", [])
    if h and "fix_commits" in h[-1]:
        ok("history has fix_commits field")
    else:
        fail("missing fix_commits in history")

    # 4. status is now implemented
    result2 = subprocess.run(
        [sys.executable, str(SCRIPT), "get", str(ITEM_DIR)],
        capture_output=True,
        text=True
    )
    status = result2.stdout.strip()
    if status == "implemented":
        ok("status is implemented")
    else:
        fail(f"status: got '{status}'")

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
