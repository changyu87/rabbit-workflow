#!/usr/bin/env python3
# test-branch-guard.py — tests for file-backlog-item.py branch guard
# and SKILL.md Working Protocol user-decision gate.
#
# t1: file-backlog-item.py on non-main branch warns and exits non-zero (no tty = bypass)
# t2: file-backlog-item.py on main branch succeeds without prompt
# t3: SKILL.md Working Protocol contains user-decision gate language

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
SKILL_SRC = FEATURE_DIR / "skills" / "rabbit-backlog" / "SKILL.md"

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


print("=== test-branch-guard.py: branch guard + SKILL.md user-decision gate ===")
print()

# Set up isolated git repo for branch guard tests
ISO_REPO = Path(tempfile.mkdtemp())
try:
    subprocess.run(["git", "-C", str(ISO_REPO), "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "config", "user.email", "test@rabbit"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "config", "user.name", "rabbit-test"], check=True)
    subprocess.run(["git", "-C", str(ISO_REPO), "commit", "--allow-empty", "-m", "init", "--quiet"], check=True)

    # Create feature.json for rabbit-backlog so find-feature.py can discover it.
    (ISO_REPO / ".claude" / "features" / "rabbit-backlog").mkdir(parents=True, exist_ok=True)
    (ISO_REPO / ".claude" / "features" / "rabbit-backlog" / "feature.json").write_text(json.dumps({
        "name": "rabbit-backlog",
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "Test feature for backlog filing tests."
    }, indent=2))

    # Rename default branch to 'main' (in case it's 'master')
    current_branch = subprocess.check_output(
        ["git", "-C", str(ISO_REPO), "branch", "--show-current"],
        text=True
    ).strip()
    if current_branch != "main":
        subprocess.run(
            ["git", "-C", str(ISO_REPO), "branch", "-m", current_branch, "main"],
            capture_output=True
        )

    # Copy scripts and contract scripts into ISO_REPO
    ISO_SCRIPTS_DIR = ISO_REPO / "scripts"
    ISO_SCRIPTS_DIR.mkdir(exist_ok=True)
    shutil.copy2(FILE_BACKLOG, ISO_SCRIPTS_DIR / "file-backlog-item.py")
    os.chmod(ISO_SCRIPTS_DIR / "file-backlog-item.py", 0o755)

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

    # t1: file-backlog-item.py on non-main branch warns (stderr) and exits non-zero when tty unavailable
    subprocess.run(
        ["git", "-C", str(ISO_REPO), "checkout", "-b", "feature/test-branch", "--quiet"],
        capture_output=True
    )

    branch_now = subprocess.check_output(
        ["git", "-C", str(ISO_REPO), "branch", "--show-current"],
        text=True
    ).strip()

    if branch_now == "feature/test-branch":
        # Run the script with stdin closed (no tty) — should output warning and exit non-zero
        result = subprocess.run(
            [sys.executable, str(ISO_FILE_BACKLOG),
             "--related-feature", "rabbit-backlog",
             "--title", "Branch guard test"],
            capture_output=True,
            text=True,
            cwd=str(ISO_REPO),
            stdin=subprocess.DEVNULL
        )

        if result.returncode != 0:
            ok("t1: non-main branch with no tty exits non-zero")
        else:
            fail_t("t1: non-main branch with no tty exits non-zero",
                   f"script exited 0 but should exit non-zero on non-main (exit={result.returncode})")
    else:
        fail_t("t1: non-main branch with no tty exits non-zero",
               f"could not set up non-main branch (got: {branch_now})")

    # t2: file-backlog-item.py on main branch succeeds without prompt
    subprocess.run(
        ["git", "-C", str(ISO_REPO), "checkout", "main", "--quiet"],
        capture_output=True
    )
    branch_main = subprocess.check_output(
        ["git", "-C", str(ISO_REPO), "branch", "--show-current"],
        text=True
    ).strip()

    if branch_main == "main":
        result = subprocess.run(
            [sys.executable, str(ISO_FILE_BACKLOG),
             "--related-feature", "rabbit-backlog",
             "--title", "Main branch test"],
            capture_output=True,
            text=True,
            cwd=str(ISO_REPO)
        )

        if result.returncode == 0:
            ok("t2: main branch succeeds without prompt")
        else:
            fail_t("t2: main branch succeeds without prompt",
                   f"script exited {result.returncode} on main branch")
    else:
        fail_t("t2: main branch succeeds without prompt",
               f"could not switch to main branch (got: {branch_main})")

finally:
    shutil.rmtree(ISO_REPO, ignore_errors=True)

# t3: SKILL.md Working Protocol section contains user-decision gate language
GATE_KEYWORDS = ["confirm", "summary", "recommend"]
all_found = True
missing = []

if SKILL_SRC.is_file():
    content = SKILL_SRC.read_text().lower()
    for kw in GATE_KEYWORDS:
        if kw not in content:
            all_found = False
            missing.append(kw)

    # Also check that the section explicitly gates on user confirmation before rabbit-feature-touch
    if "rabbit-feature-touch" not in SKILL_SRC.read_text():
        all_found = False
        missing.append("rabbit-feature-touch reference")

    if all_found:
        ok("t3: SKILL.md Working Protocol has user-decision gate language")
    else:
        fail_t("t3: SKILL.md Working Protocol has user-decision gate language",
               f"missing keywords: {' '.join(missing)}")
else:
    fail_t("t3: SKILL.md Working Protocol has user-decision gate language",
           f"SKILL.md not found: {SKILL_SRC}")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
