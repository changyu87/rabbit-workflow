#!/usr/bin/env python3
"""Tests for BACKLOG-13: CLAUDE.md gitignore + drift detection."""
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
GENERATE_SCRIPT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")
GITIGNORE = os.path.join(REPO_ROOT, ".gitignore")

failures = 0


def ok(n, msg):
    print(f"  PASS t_bl13_{n}: {msg}")


def fail_t(n, msg):
    global failures
    print(f"  FAIL t_bl13_{n}: {msg}")
    failures += 1


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


print("test-RABBIT-CAGE-BACKLOG13-claude-md-gitignore-drift.py")
print()

# t1
print("=== Invariant 71: CLAUDE.md is committed; NOT in .gitignore ===")
gi_lines = [line.strip() for line in read(GITIGNORE).splitlines()]
if "CLAUDE.md" not in gi_lines:
    ok(1, ".gitignore does NOT list CLAUDE.md as an exact entry")
else:
    fail_t(1, ".gitignore lists CLAUDE.md — must be removed so the file can be committed")

# t2
tracked = subprocess.run(["git", "-C", REPO_ROOT, "ls-files", "CLAUDE.md"],
                         capture_output=True, text=True).stdout.strip()
if tracked:
    ok(2, "CLAUDE.md is tracked by git (appears in git ls-files)")
else:
    fail_t(2, "CLAUDE.md is NOT tracked by git — must be committed to the repo")

# t3
if os.path.isfile(os.path.join(REPO_ROOT, "CLAUDE.md")):
    ok(3, "CLAUDE.md exists on disk at repo root")
else:
    fail_t(3, "CLAUDE.md does not exist on disk at repo root")

print()
print("=== Invariant 72: drift detection emits [rabbit] systemMessage warning ===")

if not (os.path.isfile(SYNC_CHECK) and os.access(SYNC_CHECK, os.X_OK)):
    fail_t(4, "sync-check.py missing or not executable — cannot test drift detection")
    print()
    print(f"Results: 0 passed, {failures} failed")
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)

if not (os.path.isfile(GENERATE_SCRIPT) and os.access(GENERATE_SCRIPT, os.X_OK)):
    fail_t(4, "generate-claude-md.py missing or not executable — cannot test drift detection")
    print()
    print(f"Results: 0 passed, {failures} failed")
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)

ok(4, "sync-check.py and generate-claude-md.py exist and are executable")

tmproot = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmproot, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(tmproot, ".claude/features/policy"), exist_ok=True)

    for fname, content in [
        ("philosophy.md", "# Philosophy\nMachine First.\n"),
        ("spec-rules.md", "# Spec Rules\nSpec.\n"),
        ("coding-rules.md", "# Coding Rules\nCode.\n"),
    ]:
        with open(os.path.join(tmproot, ".claude/features/policy", fname), "w") as f:
            f.write(content)

    with open(os.path.join(tmproot, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test header", "version": "0.0.1"}, f)

    shutil.copy(GENERATE_SCRIPT, os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md.py"))
    shutil.copy(os.path.join(os.path.dirname(GENERATE_SCRIPT), "generate-claude-md-header.py"),
                os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md-header.py"))

    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write("# Rabbit Workflow — STALE OUTDATED CONTENT\nThis is old and differs from source.\n")

    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    drift_output = res.stdout
    drift_exit = res.returncode

    # t5
    if drift_exit == 0:
        ok(5, "sync-check.py exits 0 when drift detected")
    else:
        fail_t(5, f"sync-check.py exited {drift_exit} on drift (expected 0)")

    # t6
    json_valid = False
    parsed = None
    try:
        parsed = json.loads(drift_output)
        json_valid = True
        ok(6, "sync-check.py emits valid JSON on drift")
    except Exception:
        fail_t(6, f"sync-check.py did not emit valid JSON on drift; got: '{drift_output}'")

    sys_msg_drift = parsed.get("systemMessage", "") if json_valid and parsed else ""

    # t7 — BACKLOG-19: brand is now `[🐇 rabbit 🐇]`
    if "[🐇 rabbit 🐇]" in sys_msg_drift:
        ok(7, "systemMessage contains '[🐇 rabbit 🐇]' tag on drift")
    else:
        fail_t(7, f"systemMessage does NOT contain '[🐇 rabbit 🐇]' tag on drift; got: '{sys_msg_drift}'")

    # t8
    msg_lower = sys_msg_drift.lower()
    if any(t in msg_lower for t in ("drift", "drifted", "regenerated")):
        ok(8, "systemMessage contains drift-related term (drift/drifted/regenerated)")
    else:
        fail_t(8, f"systemMessage missing drift-related term; got: '{sys_msg_drift}'")

    # t9: CLAUDE.md is now an @-import manifest (BUG-80 / generate-claude-md.py
    # no longer inlines policy bodies). Assert that the regenerated file
    # contains @-imports for the three policy files.
    cm = os.path.join(tmproot, "CLAUDE.md")
    if os.path.isfile(cm):
        regen = read(cm)
        expected_imports = ("@.claude/features/policy/philosophy.md",
                            "@.claude/features/policy/spec-rules.md",
                            "@.claude/features/policy/coding-rules.md")
        if all(imp in regen for imp in expected_imports):
            ok(9, "CLAUDE.md regenerated with current policy @-imports after drift")
        else:
            fail_t(9, f"CLAUDE.md exists but missing one or more @-imports after drift; got: {regen!r}")
    else:
        fail_t(9, "CLAUDE.md missing after drift detection — hook should regenerate it")

    print()
    print("=== BACKLOG-19 / Inv 89: first-run path REMOVED — silent exit 0, no CLAUDE.md created ===")

    tmproot2 = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmproot2, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
        os.makedirs(os.path.join(tmproot2, ".claude/features/policy"), exist_ok=True)

        for fname, content in [
            ("philosophy.md", "# Philosophy\nMachine First.\n"),
            ("spec-rules.md", "# Spec Rules\nSpec.\n"),
            ("coding-rules.md", "# Coding Rules\nCode.\n"),
        ]:
            with open(os.path.join(tmproot2, ".claude/features/policy", fname), "w") as f:
                f.write(content)

        with open(os.path.join(tmproot2, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
            json.dump({"header": "# Rabbit Workflow — test header", "version": "0.0.1"}, f)

        shutil.copy(GENERATE_SCRIPT, os.path.join(tmproot2, ".claude/features/rabbit-cage/scripts/generate-claude-md.py"))
        shutil.copy(os.path.join(os.path.dirname(GENERATE_SCRIPT), "generate-claude-md-header.py"),
                    os.path.join(tmproot2, ".claude/features/rabbit-cage/scripts/generate-claude-md-header.py"))

        # t10
        if not os.path.isfile(os.path.join(tmproot2, "CLAUDE.md")):
            ok(10, "pre-condition: CLAUDE.md absent in temp workspace")
        else:
            fail_t(10, "pre-condition failed: CLAUDE.md already exists in temp tree")

        env = {**os.environ, "RABBIT_ROOT": tmproot2, "RABBIT_SYNC_EVERY": "1"}
        res2 = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)

        # t11
        if res2.returncode == 0:
            ok(11, "sync-check.py exits 0 when CLAUDE.md absent")
        else:
            fail_t(11, f"sync-check.py exited {res2.returncode} (expected 0)")

        # t12 — BACKLOG-19: first-run path removed; sync-check no longer creates CLAUDE.md
        cm2 = os.path.join(tmproot2, "CLAUDE.md")
        if not os.path.isfile(cm2):
            ok(12, "CLAUDE.md NOT created by sync-check.py (Inv 89 — first-run path removed)")
        else:
            fail_t(12, "CLAUDE.md was created — first-run path should be removed (Inv 89)")

        # t13 — stdout should be empty (no first-run JSON)
        if res2.stdout.strip() == "":
            ok(13, "sync-check.py emits empty stdout when CLAUDE.md absent (no first-run JSON)")
        else:
            fail_t(13, f"sync-check.py emitted JSON when CLAUDE.md absent: {res2.stdout!r}")
    finally:
        shutil.rmtree(tmproot2, ignore_errors=True)
finally:
    shutil.rmtree(tmproot, ignore_errors=True)

print()
print(f"Results: {13 - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
