#!/usr/bin/env python3
"""Tests that sync-check.py does not emit drift on first run."""
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
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")

failures = 0


def ok(t, msg):
    print(f"  PASS t{t}: {msg}")


def fail_t(t, msg):
    global failures
    print(f"  FAIL t{t}: {msg}")
    failures += 1


print("test-RABBIT-CAGE-16-first-stop-no-false-drift.py")
print()

# t1
if os.path.isfile(SYNC_CHECK) and os.access(SYNC_CHECK, os.X_OK):
    ok(1, "sync-check.py exists and is executable")
else:
    fail_t(1, f"sync-check.py missing or not executable at {SYNC_CHECK}")

tmproot = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmproot, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(tmproot, ".claude/features/policy"), exist_ok=True)

    with open(os.path.join(tmproot, ".claude/features/policy/philosophy.md"), "w") as f:
        f.write("# Philosophy\nMachine First.\n")
    with open(os.path.join(tmproot, ".claude/features/policy/spec-rules.md"), "w") as f:
        f.write("# Spec Rules\nSpec.\n")
    with open(os.path.join(tmproot, ".claude/features/policy/coding-rules.md"), "w") as f:
        f.write("# Coding Rules\nCode.\n")

    with open(os.path.join(tmproot, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test header"}, f)

    shutil.copy(
        os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/generate-claude-md.py"),
        os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md.py"),
    )
    shutil.copy(
        os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/generate-claude-md-header.py"),
        os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md-header.py"),
    )

    # t2
    if not os.path.isfile(os.path.join(tmproot, "CLAUDE.md")):
        ok(2, "pre-condition: CLAUDE.md absent in temp workspace (fresh install scenario)")
    else:
        fail_t(2, "pre-condition failed: CLAUDE.md already exists in temp tree — test setup error")

    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    result = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    sync_output = result.stdout
    sync_exit = result.returncode

    # t3
    if sync_exit == 0:
        ok(3, "sync-check.py exits 0 when CLAUDE.md is absent")
    else:
        fail_t(3, f"sync-check.py exited {sync_exit} (expected 0)")

    # t4 — BACKLOG-19 / Inv 89: first-run path removed; sync-check no longer
    # creates CLAUDE.md when absent. Bootstrap is install.py's job.
    if not os.path.isfile(os.path.join(tmproot, "CLAUDE.md")):
        ok(4, "CLAUDE.md NOT created by sync-check.py (Inv 89 — first-run path removed)")
    else:
        fail_t(4, "CLAUDE.md was created — first-run path should be removed (Inv 89)")

    # Extract systemMessage
    sys_msg = ""
    try:
        d = json.loads(sync_output)
        sys_msg = d.get("systemMessage", "")
    except Exception:
        pass

    # t5
    if "drift" in sys_msg.lower():
        fail_t(5, f"systemMessage contains 'drift' when CLAUDE.md absent — should NOT; got: '{sys_msg}'")
    else:
        ok(5, "systemMessage does NOT contain 'drift' when CLAUDE.md absent")

    # t6 — BACKLOG-19: when CLAUDE.md absent, hook exits silently (no JSON).
    if not sys_msg:
        ok(6, "no systemMessage emitted when CLAUDE.md absent (Inv 89 — silent exit)")
    else:
        fail_t(6, f"systemMessage should be empty/absent; got: '{sys_msg}'")
finally:
    shutil.rmtree(tmproot, ignore_errors=True)

print()
print(f"Results: {6 - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
