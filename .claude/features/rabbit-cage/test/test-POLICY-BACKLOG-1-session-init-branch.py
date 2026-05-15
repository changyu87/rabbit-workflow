#!/usr/bin/env python3
"""Tests session-init.py does not create session/ branches."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
HOOK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def make_repo():
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", d, "checkout", "-q", "-b", "main"], capture_output=True)
    open(os.path.join(d, "placeholder"), "a").close()
    subprocess.run(["git", "-C", d, "add", "placeholder"], check=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    os.makedirs(os.path.join(d, ".claude"), exist_ok=True)
    with open(os.path.join(d, "CLAUDE.md"), "w") as f:
        f.write("# Test CLAUDE.md\n")
    return d


print("test-POLICY-BACKLOG-1-session-init-branch.py")
print()

repos = []

try:
    # t1
    print("=== t1: on main → branch unchanged ===")
    repo1 = make_repo()
    repos.append(repo1)
    env = {**os.environ, "RABBIT_ROOT": repo1}
    subprocess.run([sys.executable, HOOK], env=env, capture_output=True)
    branch = subprocess.run(["git", "-C", repo1, "branch", "--show-current"],
                            capture_output=True, text=True).stdout.strip()
    if branch == "main":
        ok("hook left branch unchanged at 'main'")
    else:
        fail_t(f"hook changed branch from 'main' to '{branch}' (R1 branch creation should be removed)")

    # t2
    print()
    print("=== t2: on feature branch → no branch change ===")
    repo2 = make_repo()
    repos.append(repo2)
    subprocess.run(["git", "-C", repo2, "checkout", "-q", "-b", "feature/keep-this"], capture_output=True)
    env = {**os.environ, "RABBIT_ROOT": repo2}
    subprocess.run([sys.executable, HOOK], env=env, capture_output=True)
    branch = subprocess.run(["git", "-C", repo2, "branch", "--show-current"],
                            capture_output=True, text=True).stdout.strip()
    if branch == "feature/keep-this":
        ok("hook left branch unchanged at 'feature/keep-this'")
    else:
        fail_t(f"hook changed branch from 'feature/keep-this' to '{branch}'")

    # t3
    print()
    print("=== t3: @-import injection emits valid JSON ===")
    env = {**os.environ, "RABBIT_ROOT": REPO_ROOT}
    res = subprocess.run([sys.executable, HOOK], env=env, capture_output=True, text=True)
    try:
        d = json.loads(res.stdout)
        if "additionalContext" in d:
            ok("@-import injection emits valid JSON with additionalContext")
        else:
            fail_t("@-import injection did not emit valid JSON with additionalContext")
    except Exception:
        fail_t("@-import injection did not emit valid JSON with additionalContext")
finally:
    for r in repos:
        shutil.rmtree(r, ignore_errors=True)

print()
if failures == 0:
    print(f"test-POLICY-BACKLOG-1-session-init-branch.py: ALL {total} PASSED")
    sys.exit(0)
else:
    print(f"test-POLICY-BACKLOG-1-session-init-branch.py: {failures}/{total} FAILED")
    sys.exit(1)
