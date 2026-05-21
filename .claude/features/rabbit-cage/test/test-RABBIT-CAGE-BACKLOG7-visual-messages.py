#!/usr/bin/env python3
"""Tests that all three hooks emit system messages with emoji + box-drawing chars."""
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
SESSION_INIT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py")
REFRESH_HOOK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/refresh.py")

failures = 0
total = 0

BORDER_CHARS = set("━─═╔╗╚╝║╠╣╦╩╬┌┐└┘│├┤┬┴┼")


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


def extract_sys_msg(output):
    try:
        d = json.loads(output)
        return d.get("systemMessage", "")
    except Exception:
        return ""


def assert_visual_msg(label, msg):
    if not msg:
        fail_t(f"{label} — systemMessage is empty (no output emitted)")
        return
    has_emoji = any(ord(c) > 0x2600 for c in msg)
    has_border = any(c in BORDER_CHARS for c in msg)
    if has_emoji and has_border:
        ok(f"{label} — systemMessage contains emoji AND box-drawing border chars")
    elif not has_emoji and not has_border:
        fail_t(f"{label} — systemMessage has NEITHER emoji NOR border chars; got: '{msg}'")
    elif not has_emoji:
        fail_t(f"{label} — systemMessage has border chars but NO emoji; got: '{msg}'")
    else:
        fail_t(f"{label} — systemMessage has emoji but NO border chars; got: '{msg}'")


def build_tmproot():
    tmproot = tempfile.mkdtemp()
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
        json.dump({"header": "# Rabbit Workflow — test header"}, f)

    for fname in ("generate-claude-md.py", "generate-claude-md-header.py"):
        shutil.copy(
            os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts", fname),
            os.path.join(tmproot, ".claude/features/rabbit-cage/scripts", fname),
        )

    with open(os.path.join(tmproot, ".claude/features/registry.json"), "w") as f:
        json.dump({"schema_version": "1.0.0", "features": {}}, f)
    return tmproot


print("test-RABBIT-CAGE-BACKLOG7-visual-messages.py")
print()

tmproots = []
try:
    # Test 1: drift case
    tmproot1 = build_tmproot()
    tmproots.append(tmproot1)
    with open(os.path.join(tmproot1, "CLAUDE.md"), "w") as f:
        f.write("STALE CONTENT\n")

    env = {**os.environ, "RABBIT_ROOT": tmproot1, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    drift_msg = extract_sys_msg(res.stdout)
    assert_visual_msg("sync-check.py DRIFT case", drift_msg)

    # Test 2: surface drift
    # BACKLOG-21 (Inv 88): surface drift is detected by comparing
    # build-contract.json copy-file source/destination sha256 in-process.
    tmproot2 = build_tmproot()
    tmproots.append(tmproot2)
    env = {**os.environ, "RABBIT_ROOT": tmproot2}
    res = subprocess.run([sys.executable, os.path.join(tmproot2, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
                         env=env, capture_output=True, text=True)
    with open(os.path.join(tmproot2, "CLAUDE.md"), "w") as f:
        f.write(res.stdout.rstrip("\n") + "\n")

    os.makedirs(os.path.join(tmproot2, "src"), exist_ok=True)
    os.makedirs(os.path.join(tmproot2, "dst"), exist_ok=True)
    with open(os.path.join(tmproot2, "src/x.py"), "w") as f:
        f.write("source\n")
    with open(os.path.join(tmproot2, "dst/x.py"), "w") as f:
        f.write("destination stale\n")
    os.makedirs(os.path.join(tmproot2, ".claude/features/contract"), exist_ok=True)
    with open(os.path.join(tmproot2, ".claude/features/contract/build-contract.json"), "w") as f:
        json.dump({
            "schema_version": "1.0.0",
            "owner": "test",
            "deprecation_criterion": "test",
            "targets": [{
                "name": "hooks/x.py",
                "type": "copy-file",
                "source": "src/x.py",
                "destination": "dst/x.py",
                "check_on_stop": True,
            }],
        }, f)

    env = {**os.environ, "RABBIT_ROOT": tmproot2, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    skills_msg = extract_sys_msg(res.stdout)
    assert_visual_msg("sync-check.py SURFACE DRIFT case", skills_msg)

    # Test 3: session-init
    tmproot3 = build_tmproot()
    tmproots.append(tmproot3)
    with open(os.path.join(tmproot3, "CLAUDE.md"), "w") as f:
        f.write("# Rabbit Workflow — test header\n\n@.claude/features/policy/philosophy.md\n@.claude/features/policy/spec-rules.md\n@.claude/features/policy/coding-rules.md\n")

    # BUG-39: Python-only stack — no .sh stubs.

    env = {**os.environ, "RABBIT_ROOT": tmproot3}
    res = subprocess.run([sys.executable, SESSION_INIT], env=env, capture_output=True, text=True)
    init_msg = extract_sys_msg(res.stdout)
    assert_visual_msg("session-init.py session-start injection", init_msg)

    # Test 4: refresh.py — refresh now uses only @-imports (BUG-80 removed
    # the inline rabbit-policy-start/end section detection).
    tmproot4 = build_tmproot()
    tmproots.append(tmproot4)
    with open(os.path.join(tmproot4, "CLAUDE.md"), "w") as f:
        f.write(
            "# Rabbit Workflow — test header\n\n"
            "@.claude/features/policy/philosophy.md\n"
            "@.claude/features/policy/spec-rules.md\n"
            "@.claude/features/policy/coding-rules.md\n"
        )

    THRESHOLD = "5"
    with open(os.path.join(tmproot4, ".rabbit-prompt-counter"), "w") as f:
        f.write(THRESHOLD + "\n")

    env = {**os.environ, "RABBIT_ROOT": tmproot4, "RABBIT_REFRESH_EVERY": THRESHOLD}
    res = subprocess.run([sys.executable, REFRESH_HOOK], env=env, capture_output=True, text=True)
    refresh_msg = extract_sys_msg(res.stdout)
    assert_visual_msg("refresh.py periodic refresh", refresh_msg)
finally:
    for d in tmproots:
        shutil.rmtree(d, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
