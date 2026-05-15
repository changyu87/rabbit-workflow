#!/usr/bin/env python3
# test-backlog-scripts.py — tests for centralized storage + per-feature ID scheme.
#
# New design being tested:
#   - file-backlog-item.py uses --related-feature <name> (not --dir / --name)
#   - Items written to .claude/backlogs/<feature-name>/<PREFIX>-BACKLOG-<N>/item.json
#   - ID scheme: <FEATURE-NAME-UPPERCASED>-BACKLOG-<N> (per-feature counter)
#   - feature.json must NOT contain bugs_root or backlog_root
#   - .claude/backlogs/rabbit-cage/ must exist with RABBIT-CAGE-BACKLOG-1..6

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

FILE_BACKLOG = SCRIPTS_DIR / "file-backlog-item.py"
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


print("=== test-backlog-scripts.py: centralized storage + per-feature ID ===")
print()

# t1: scripts/file-backlog-item.py exists and is executable
if FILE_BACKLOG.is_file() and os.access(FILE_BACKLOG, os.X_OK):
    ok("t1: file-backlog-item.py exists and is executable")
else:
    fail_t("t1: file-backlog-item.py exists and is executable",
           f"not found or not executable: {FILE_BACKLOG}")

# t2: scripts/backlog-item-status.py exists and is executable
if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
    ok("t2: backlog-item-status.py exists and is executable")
else:
    fail_t("t2: backlog-item-status.py exists and is executable",
           f"not found or not executable: {ITEM_STATUS}")

# ---------------------------------------------------------------------------
# Isolated git repo for t3–t6.
#
# file-backlog-item.py resolves REPO_ROOT via:
#   git -C os.path.dirname(os.path.abspath(__file__)) rev-parse --show-toplevel
# So the script must run from a directory INSIDE ISO_REPO.
# We copy the scripts into ISO_REPO/scripts/ so dirname resolves there.
# ---------------------------------------------------------------------------
ISO_REPO = Path(tempfile.mkdtemp())

try:
    subprocess.run(["git", "-C", str(ISO_REPO), "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "config", "user.name", "rabbit-test"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)
    # Ensure the default branch is named 'main' for branch guard compatibility.
    init_branch = subprocess.check_output(
        ["git", "-C", str(ISO_REPO), "branch", "--show-current"],
        text=True
    ).strip()
    if init_branch != "main":
        subprocess.run(
            ["git", "-C", str(ISO_REPO), "branch", "-m", init_branch, "main"],
            capture_output=True
        )

    # Create feature.json for rabbit-backlog so find-feature.py can discover it.
    feat_dir = ISO_REPO / ".claude" / "features" / "rabbit-backlog"
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / "feature.json").write_text(json.dumps({
        "name": "rabbit-backlog",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "Test feature for backlog filing tests."
    }, indent=2))

    # Copy scripts into ISO_REPO so dirname "$0" resolves inside ISO_REPO.
    ISO_SCRIPTS_DIR = ISO_REPO / "scripts"
    ISO_SCRIPTS_DIR.mkdir(exist_ok=True)
    shutil.copy2(FILE_BACKLOG, ISO_SCRIPTS_DIR / "file-backlog-item.py")
    shutil.copy2(ITEM_STATUS, ISO_SCRIPTS_DIR / "backlog-item-status.py")
    os.chmod(ISO_SCRIPTS_DIR / "file-backlog-item.py", 0o755)
    os.chmod(ISO_SCRIPTS_DIR / "backlog-item-status.py", 0o755)

    # Copy workspace-map.py and find-feature.py to the expected contract path inside ISO_REPO.
    ISO_CONTRACT_SCRIPTS = ISO_REPO / ".claude" / "features" / "contract" / "scripts"
    ISO_CONTRACT_SCRIPTS.mkdir(parents=True, exist_ok=True)
    WORKSPACE_MAP_SRC = REPO_ROOT / ".claude" / "features" / "contract" / "scripts" / "workspace-map.py"
    FIND_FEATURE_SRC = REPO_ROOT / ".claude" / "features" / "contract" / "scripts" / "find-feature.py"
    if WORKSPACE_MAP_SRC.is_file():
        shutil.copy2(WORKSPACE_MAP_SRC, ISO_CONTRACT_SCRIPTS / "workspace-map.py")
        os.chmod(ISO_CONTRACT_SCRIPTS / "workspace-map.py", 0o755)
    if FIND_FEATURE_SRC.is_file():
        shutil.copy2(FIND_FEATURE_SRC, ISO_CONTRACT_SCRIPTS / "find-feature.py")
        os.chmod(ISO_CONTRACT_SCRIPTS / "find-feature.py", 0o755)

    ISO_FILE_BACKLOG = ISO_SCRIPTS_DIR / "file-backlog-item.py"
    ISO_CENTRAL_BACKLOGS = ISO_REPO / ".claude" / "backlogs"

    # t3: file-backlog-item.py --related-feature rabbit-backlog creates item at centralized path
    ISO_EXPECTED_DIR = ISO_CENTRAL_BACKLOGS / "rabbit-backlog" / "RABBIT-BACKLOG-BACKLOG-1"
    ISO_EXPECTED_ITEM = ISO_EXPECTED_DIR / "item.json"

    if FILE_BACKLOG.is_file() and os.access(FILE_BACKLOG, os.X_OK):
        result = subprocess.run(
            [sys.executable, str(ISO_FILE_BACKLOG),
             "--related-feature", "rabbit-backlog",
             "--title", "Test item"],
            capture_output=True,
            text=True,
            cwd=str(ISO_REPO)
        )
        if result.returncode == 0:
            if ISO_EXPECTED_ITEM.is_file():
                ok("t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json")
            else:
                fail_t("t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json",
                       f"item.json not at expected path: {ISO_EXPECTED_ITEM}")
        else:
            fail_t("t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json",
                   "script exited non-zero")
    else:
        fail_t("t3: --related-feature creates .claude/backlogs/rabbit-backlog/RABBIT-BACKLOG-BACKLOG-1/item.json",
               "script not found or not executable")

    # t4: created item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened
    if ISO_EXPECTED_ITEM.is_file():
        d = json.loads(ISO_EXPECTED_ITEM.read_text())
        issues = []
        if d.get("status") != "open":
            issues.append(f"status={d.get('status')!r} (want 'open')")
        if d.get("name") != "RABBIT-BACKLOG-BACKLOG-1":
            issues.append(f"name={d.get('name')!r} (want 'RABBIT-BACKLOG-BACKLOG-1')")
        h = d.get("history", [])
        first_action = h[0].get("action") if h else "missing"
        if first_action != "opened":
            issues.append(f"history[0].action={first_action!r} (want 'opened')")
        if not issues:
            ok("t4: item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened")
        else:
            fail_t("t4: item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened",
                   "; ".join(issues))
    else:
        fail_t("t4: item.json has status=open, name=RABBIT-BACKLOG-BACKLOG-1, history[0].action=opened",
               "item.json not found (t3 prerequisite failed)")

    # t5: a second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments per-feature)
    ISO_EXPECTED_ITEM2 = ISO_CENTRAL_BACKLOGS / "rabbit-backlog" / "RABBIT-BACKLOG-BACKLOG-2" / "item.json"

    if FILE_BACKLOG.is_file() and os.access(FILE_BACKLOG, os.X_OK):
        result = subprocess.run(
            [sys.executable, str(ISO_FILE_BACKLOG),
             "--related-feature", "rabbit-backlog",
             "--title", "Second test item"],
            capture_output=True,
            text=True,
            cwd=str(ISO_REPO)
        )
        if result.returncode == 0:
            if ISO_EXPECTED_ITEM2.is_file():
                ok("t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)")
            else:
                fail_t("t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)",
                       f"item.json not at: {ISO_EXPECTED_ITEM2}")
        else:
            fail_t("t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)",
                   "script exited non-zero on second call")
    else:
        fail_t("t5: second call creates RABBIT-BACKLOG-BACKLOG-2 (counter increments)",
               "script not found or not executable")

    # t6: --related-feature nonexistent-xyz fails with non-zero exit (registry validation)
    if FILE_BACKLOG.is_file() and os.access(FILE_BACKLOG, os.X_OK):
        result = subprocess.run(
            [sys.executable, str(ISO_FILE_BACKLOG),
             "--related-feature", "nonexistent-xyz",
             "--title", "Should fail"],
            capture_output=True,
            text=True,
            cwd=str(ISO_REPO)
        )
        if result.returncode == 0:
            fail_t("t6: --related-feature nonexistent-xyz fails with non-zero exit",
                   "command succeeded but should have failed (registry validation)")
        else:
            ok("t6: --related-feature nonexistent-xyz fails with non-zero exit")
    else:
        fail_t("t6: --related-feature nonexistent-xyz fails with non-zero exit",
               "script not found or not executable")

finally:
    shutil.rmtree(ISO_REPO, ignore_errors=True)

# t7: backlog-item-status.py set ITEM_DIR in-progress succeeds
TMPDIR_T7 = Path(tempfile.mkdtemp())
TMPDIR_T8 = Path(tempfile.mkdtemp())

try:
    (TMPDIR_T7 / "item.json").write_text(json.dumps({
        "name": "DUMMY-T7",
        "title": "t7 item",
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

    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = subprocess.run(
            [sys.executable, str(ITEM_STATUS), "set", str(TMPDIR_T7), "in-progress",
             "--reason", "starting work"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            ok("t7: backlog-item-status.py set in-progress succeeds")
        else:
            fail_t("t7: backlog-item-status.py set in-progress succeeds",
                   "set in-progress exited non-zero")
    else:
        fail_t("t7: backlog-item-status.py set in-progress succeeds",
               "backlog-item-status.py not found or not executable")

    # t8: backlog-item-status.py direct open-to-done is denied (invalid status)
    (TMPDIR_T8 / "item.json").write_text(json.dumps({
        "name": "DUMMY-T8",
        "title": "t8 item",
        "status": "open",
        "priority": "low",
        "description": "",
        "owner": "test",
        "filed": "2026-05-11T00:00:00Z",
        "filed_by": "test",
        "closed": None,
        "history": [
            {"ts": "2026-05-11T00:00:00Z", "actor": "test", "action": "opened", "note": "initial filing"}
        ]
    }, indent=2))

    if ITEM_STATUS.is_file() and os.access(ITEM_STATUS, os.X_OK):
        result = subprocess.run(
            [sys.executable, str(ITEM_STATUS), "set", str(TMPDIR_T8), "done"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            fail_t("t8: direct open-to-done is denied",
                   "transition succeeded but should be denied")
        else:
            ok("t8: direct open-to-done is denied")
    else:
        fail_t("t8: direct open-to-done is denied",
               "backlog-item-status.py not found or not executable")

finally:
    shutil.rmtree(TMPDIR_T7, ignore_errors=True)
    shutil.rmtree(TMPDIR_T8, ignore_errors=True)

# t9: feature.json does NOT contain bugs_root or backlog_root key
FEATURE_JSON = FEATURE_DIR / "feature.json"
if FEATURE_JSON.is_file():
    d = json.loads(FEATURE_JSON.read_text())
    found = [k for k in ("bugs_root", "backlog_root") if k in d]
    if not found:
        ok("t9: feature.json does NOT contain bugs_root or backlog_root")
    else:
        fail_t("t9: feature.json does NOT contain bugs_root or backlog_root",
               f"found forbidden keys: {', '.join(found)}")
else:
    fail_t("t9: feature.json does NOT contain bugs_root or backlog_root",
           f"feature.json not found: {FEATURE_JSON}")

# t10: workspace-map.py backlog rabbit-cage returns expected path convention
WORKSPACE_MAP_BIN = REPO_ROOT / ".claude" / "features" / "contract" / "scripts" / "workspace-map.py"
if WORKSPACE_MAP_BIN.is_file():
    env = os.environ.copy()
    env["RABBIT_ROOT"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, str(WORKSPACE_MAP_BIN), "backlog", "rabbit-cage"],
        capture_output=True,
        text=True,
        env=env
    )
    wm_out = result.stdout.strip()
    expected_suffix = ".claude/backlogs/rabbit-cage"
    if wm_out.endswith(expected_suffix):
        ok("t10: workspace-map.py backlog rabbit-cage returns expected path")
    else:
        fail_t("t10: workspace-map.py backlog rabbit-cage returns expected path",
               f"got: '{wm_out}' (expected suffix: '{expected_suffix}')")
else:
    fail_t("t10: workspace-map.py backlog rabbit-cage returns expected path",
           f"workspace-map.py not found: {WORKSPACE_MAP_BIN}")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
