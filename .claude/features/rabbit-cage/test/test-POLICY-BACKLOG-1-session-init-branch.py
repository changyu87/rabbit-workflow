#!/usr/bin/env python3
"""Tests session-init.py branch behavior (Inv 41 — R1 enforcement REMOVED).

After spec v3.12.0, session-init.py MUST NOT auto-create or auto-switch git
branches on main/master. The legacy R1 enforcement (auto-creating
session/YYYYMMDD-HHMMSS) is removed. This test asserts the no-op behavior
on both main and feature branches, and verifies @-import policy injection
still emits valid JSON.
"""
import json
import os
import re
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
    # t1: Inv 41 — on main, session-init.py MUST NOT create any branch.
    print("=== t1: on main → NO branch creation (Inv 41 — R1 removed) ===")
    repo1 = make_repo()
    repos.append(repo1)
    env = {**os.environ, "RABBIT_ROOT": repo1}
    subprocess.run([sys.executable, HOOK], env=env, capture_output=True)
    branch = subprocess.run(["git", "-C", repo1, "branch", "--show-current"],
                            capture_output=True, text=True).stdout.strip()
    if branch == "main":
        ok("hook left branch unchanged at 'main' (Inv 41 — R1 removed)")
    else:
        fail_t(f"hook switched branch from 'main' to '{branch}' (Inv 41 violation — R1 was removed)")

    # t2: on feature branch → no branch change (unchanged behavior).
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

    # t3: @-import injection emits valid JSON.
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

    # t4: emitted JSON systemMessage MUST NOT contain "R1:" or "session/" prefix.
    print()
    print("=== t4: no R1/session-branch text in systemMessage (Inv 41) ===")
    repo4 = make_repo()
    repos.append(repo4)
    env = {**os.environ, "RABBIT_ROOT": repo4}
    res = subprocess.run([sys.executable, HOOK], env=env, capture_output=True, text=True)
    out = res.stdout or ""
    has_r1 = bool(re.search(r"\bR1\b|session/\d{8}-\d{6}|checkout\s*-b", out))
    if not has_r1:
        ok("hook output contains no R1/session-branch text on main (Inv 41)")
    else:
        fail_t(f"hook output mentions R1 or session-branch text: {out!r}")
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
