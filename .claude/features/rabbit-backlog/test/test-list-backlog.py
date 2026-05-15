#!/usr/bin/env python3
# test-list-backlog.py — tests for list-backlog.py (lists backlog items with filtering).
#
# Tests verify:
#   t1: list-backlog.py exists and is executable
#   t2: default output is a valid JSON array
#   t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line
#   t4: --status filter returns only items with matching status
#   t5: --feature filter returns only items from named feature
#   t6: --feature with comma-separated values returns items from all named features
#   t7: --status with no matches outputs [] (JSON) or "(no items)" (text)
#   t8: -h/--help exits 0

import subprocess
import sys
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(subprocess.check_output(
    ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
    text=True
).strip())
FEATURE_DIR = REPO_ROOT / ".claude" / "features" / "rabbit-backlog"
SCRIPTS_DIR = FEATURE_DIR / "scripts"

LIST_BACKLOG = SCRIPTS_DIR / "list-backlog.py"

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


print("=== test-list-backlog.py: list-backlog.py spec behaviors ===")
print()

# t1: list-backlog.py exists and is executable
if LIST_BACKLOG.is_file() and os.access(LIST_BACKLOG, os.X_OK):
    ok("t1: list-backlog.py exists and is executable")
else:
    fail_t("t1: list-backlog.py exists and is executable",
           f"not found or not executable: {LIST_BACKLOG}")

# Isolated environment with fake backlog items for testing filters and output.
ISO_REPO = Path(tempfile.mkdtemp())
try:
    (ISO_REPO / ".claude" / "backlogs" / "feature-alpha" / "FEATURE-ALPHA-BACKLOG-1").mkdir(parents=True)
    (ISO_REPO / ".claude" / "backlogs" / "feature-alpha" / "FEATURE-ALPHA-BACKLOG-2").mkdir(parents=True)
    (ISO_REPO / ".claude" / "backlogs" / "feature-beta" / "FEATURE-BETA-BACKLOG-1").mkdir(parents=True)

    (ISO_REPO / ".claude" / "backlogs" / "feature-alpha" / "FEATURE-ALPHA-BACKLOG-1" / "item.json").write_text(json.dumps({
        "name": "FEATURE-ALPHA-BACKLOG-1",
        "title": "Alpha item one",
        "status": "open",
        "priority": "high",
        "description": "",
        "owner": "tester",
        "filed": "2026-05-12T00:00:00Z",
        "filed_by": "tester",
        "closed": None,
        "fix_commits": [],
        "history": []
    }, indent=2))

    (ISO_REPO / ".claude" / "backlogs" / "feature-alpha" / "FEATURE-ALPHA-BACKLOG-2" / "item.json").write_text(json.dumps({
        "name": "FEATURE-ALPHA-BACKLOG-2",
        "title": "Alpha item two",
        "status": "in-progress",
        "priority": "medium",
        "description": "",
        "owner": "tester",
        "filed": "2026-05-12T00:00:00Z",
        "filed_by": "tester",
        "closed": None,
        "fix_commits": [],
        "history": []
    }, indent=2))

    (ISO_REPO / ".claude" / "backlogs" / "feature-beta" / "FEATURE-BETA-BACKLOG-1" / "item.json").write_text(json.dumps({
        "name": "FEATURE-BETA-BACKLOG-1",
        "title": "Beta item one",
        "status": "implemented",
        "priority": "low",
        "description": "",
        "owner": "tester",
        "filed": "2026-05-12T00:00:00Z",
        "filed_by": "tester",
        "closed": "2026-05-12T01:00:00Z",
        "fix_commits": ["abc123"],
        "history": []
    }, indent=2))

    # Copy list-backlog.py into isolated environment so RABBIT_ROOT can be set
    ISO_SCRIPTS_DIR = ISO_REPO / "scripts"
    ISO_SCRIPTS_DIR.mkdir(exist_ok=True)
    ISO_LIST_BACKLOG = ISO_SCRIPTS_DIR / "list-backlog.py"
    if LIST_BACKLOG.is_file() and os.access(LIST_BACKLOG, os.X_OK):
        shutil.copy2(LIST_BACKLOG, ISO_LIST_BACKLOG)
        os.chmod(ISO_LIST_BACKLOG, 0o755)

    def run_list(*args):
        env = os.environ.copy()
        env["RABBIT_ROOT"] = str(ISO_REPO)
        return subprocess.run(
            [sys.executable, str(ISO_LIST_BACKLOG)] + list(args),
            capture_output=True,
            text=True,
            env=env
        )

    # t2: default output is a valid JSON array containing all items
    if ISO_LIST_BACKLOG.is_file() and os.access(ISO_LIST_BACKLOG, os.X_OK):
        result = run_list()
        out = result.stdout + result.stderr
        try:
            data = json.loads(out)
            if isinstance(data, list):
                count = len(data)
                if count == 3:
                    ok(f"t2: default output is a valid JSON array with all items (count={count})")
                else:
                    fail_t("t2: default output is a valid JSON array with all items",
                           f"expected 3 items, got {count}")
            else:
                fail_t("t2: default output is a valid JSON array with all items",
                       f"output is not a list: {out}")
        except json.JSONDecodeError:
            fail_t("t2: default output is a valid JSON array with all items",
                   f"output is not valid JSON array: {out}")
    else:
        fail_t("t2: default output is a valid JSON array with all items",
               "list-backlog.py not executable")

    # t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line
    if ISO_LIST_BACKLOG.is_file() and os.access(ISO_LIST_BACKLOG, os.X_OK):
        result = run_list("--text")
        out = result.stdout + result.stderr
        if re.search(r'^\S+  \[[^\]]+\]  \[[^\]]+\]  .+$', out, re.MULTILINE):
            if "FEATURE-ALPHA-BACKLOG-1  [open]  [high]  Alpha item one" in out:
                ok("t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line")
            else:
                fail_t("t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line",
                       f"expected 'FEATURE-ALPHA-BACKLOG-1  [open]  [high]  Alpha item one' in output; got: {out}")
        else:
            fail_t("t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line",
                   f"output lines do not match expected format; got: {out}")
    else:
        fail_t("t3: --text flag prints NAME  [STATUS]  [PRIORITY]  TITLE per line",
               "list-backlog.py not executable")

    # t4: --status filter returns only items with matching status
    if ISO_LIST_BACKLOG.is_file() and os.access(ISO_LIST_BACKLOG, os.X_OK):
        result = run_list("--status", "open")
        out = result.stdout + result.stderr
        try:
            data = json.loads(out)
            if isinstance(data, list):
                count = len(data)
                non_open = sum(1 for item in data if item.get("status") != "open")
                if count == 1 and non_open == 0:
                    ok(f"t4: --status open returns only open items (count={count})")
                else:
                    fail_t("t4: --status open returns only open items",
                           f"expected 1 open item with 0 non-open, got count={count} non_open={non_open}; out={out}")
            else:
                fail_t("t4: --status open returns only open items",
                       f"output is not valid JSON array: {out}")
        except json.JSONDecodeError:
            fail_t("t4: --status open returns only open items",
                   f"output is not valid JSON array: {out}")
    else:
        fail_t("t4: --status open returns only open items",
               "list-backlog.py not executable")

    # t5: --feature filter returns only items from named feature
    if ISO_LIST_BACKLOG.is_file() and os.access(ISO_LIST_BACKLOG, os.X_OK):
        result = run_list("--feature", "feature-beta")
        out = result.stdout + result.stderr
        try:
            data = json.loads(out)
            if isinstance(data, list):
                count = len(data)
                names = [item.get("name") for item in data]
                if count == 1 and "FEATURE-BETA-BACKLOG-1" in names:
                    ok(f"t5: --feature feature-beta returns only beta items (count={count})")
                else:
                    fail_t("t5: --feature feature-beta returns only beta items",
                           f"expected 1 item with FEATURE-BETA-BACKLOG-1, got count={count} names={names}")
            else:
                fail_t("t5: --feature feature-beta returns only beta items",
                       f"output is not valid JSON array: {out}")
        except json.JSONDecodeError:
            fail_t("t5: --feature feature-beta returns only beta items",
                   f"output is not valid JSON array: {out}")
    else:
        fail_t("t5: --feature feature-beta returns only beta items",
               "list-backlog.py not executable")

    # t6: --feature with comma-separated values returns items from all named features
    if ISO_LIST_BACKLOG.is_file() and os.access(ISO_LIST_BACKLOG, os.X_OK):
        result = run_list("--feature", "feature-alpha,feature-beta")
        out = result.stdout + result.stderr
        try:
            data = json.loads(out)
            if isinstance(data, list):
                count = len(data)
                if count == 3:
                    ok(f"t6: --feature with comma-separated values returns items from all named features (count={count})")
                else:
                    fail_t("t6: --feature with comma-separated values returns items from all named features",
                           f"expected 3 items, got {count}; out={out}")
            else:
                fail_t("t6: --feature with comma-separated values returns items from all named features",
                       f"output is not valid JSON array: {out}")
        except json.JSONDecodeError:
            fail_t("t6: --feature with comma-separated values returns items from all named features",
                   f"output is not valid JSON array: {out}")
    else:
        fail_t("t6: --feature with comma-separated values returns items from all named features",
               "list-backlog.py not executable")

    # t7: --status with no matches outputs [] (JSON mode)
    if ISO_LIST_BACKLOG.is_file() and os.access(ISO_LIST_BACKLOG, os.X_OK):
        result = run_list("--status", "reopened")
        out = (result.stdout + result.stderr).strip()
        if out == "[]":
            ok("t7: --status reopened (no matches) outputs [] in JSON mode")
        else:
            fail_t("t7: --status reopened (no matches) outputs [] in JSON mode",
                   f"expected '[]', got: {out}")
    else:
        fail_t("t7: --status reopened (no matches) outputs [] in JSON mode",
               "list-backlog.py not executable")

finally:
    shutil.rmtree(ISO_REPO, ignore_errors=True)

# t8: -h/--help exits 0
if LIST_BACKLOG.is_file() and os.access(LIST_BACKLOG, os.X_OK):
    result = subprocess.run(
        [sys.executable, str(LIST_BACKLOG), "--help"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        ok("t8: --help exits 0")
    else:
        fail_t("t8: --help exits 0", "exited non-zero")
else:
    fail_t("t8: --help exits 0", "list-backlog.py not executable")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
