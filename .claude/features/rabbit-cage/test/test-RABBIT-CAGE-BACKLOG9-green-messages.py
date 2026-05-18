#!/usr/bin/env python3
"""Tests that all hook systemMessage strings are wrapped in ANSI deep-green codes."""
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
GREEN = "\x1b[32m"
RED = "\x1b[31m"
RESET = "\x1b[0m"


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


def assert_green_msg(label, msg):
    if not msg:
        fail_t(f"{label} — systemMessage is empty (no output emitted)")
        return
    if GREEN in msg and RESET in msg:
        ok(f"{label} — systemMessage contains ANSI deep-green wrap (\\x1b[32m … \\x1b[0m)")
    else:
        fail_t(f"{label} — systemMessage missing ANSI green codes; got: {msg!r}")


def assert_red_msg(label, msg):
    if not msg:
        fail_t(f"{label} — systemMessage is empty (no output emitted)")
        return
    if RED in msg and RESET in msg:
        ok(f"{label} — systemMessage contains ANSI red wrap (\\x1b[31m … \\x1b[0m)")
    else:
        fail_t(f"{label} — systemMessage missing ANSI red codes; got: {msg!r}")


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


def run_sync(tmproot, every="1"):
    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": every}
    return subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True).stdout


print("test-RABBIT-CAGE-BACKLOG9-green-messages.py")
print()

tmproots = []
try:
    # Test 1: first-run
    tmp_fr = build_tmproot()
    tmproots.append(tmp_fr)
    msg = extract_sys_msg(run_sync(tmp_fr))
    assert_green_msg("sync-check.py FIRST-RUN case", msg)

    # Test 2: drift
    tmp1 = build_tmproot()
    tmproots.append(tmp1)
    with open(os.path.join(tmp1, "CLAUDE.md"), "w") as f:
        f.write("STALE CONTENT\n")
    msg = extract_sys_msg(run_sync(tmp1))
    assert_red_msg("sync-check.py DRIFT case", msg)

    # Test 3: surface drift
    tmp2 = build_tmproot()
    tmproots.append(tmp2)
    env = {**os.environ, "RABBIT_ROOT": tmp2}
    res = subprocess.run([sys.executable, os.path.join(tmp2, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
                         env=env, capture_output=True, text=True)
    with open(os.path.join(tmp2, "CLAUDE.md"), "w") as f:
        f.write(res.stdout.rstrip("\n") + "\n")

    os.makedirs(os.path.join(tmp2, ".claude/features/rabbit-cage/test"), exist_ok=True)
    fakesurf = os.path.join(tmp2, ".claude/features/rabbit-cage/test/test-generated-surface.py")
    with open(fakesurf, "w") as f:
        f.write("#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n")
    os.chmod(fakesurf, 0o755)
    fakebuild = os.path.join(tmp2, ".claude/features/rabbit-cage/scripts/build.py")
    with open(fakebuild, "w") as f:
        f.write("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
    os.chmod(fakebuild, 0o755)

    msg = extract_sys_msg(run_sync(tmp2))
    # Inv 62: surface-drift is an alert condition; it MUST be red, not green.
    assert_red_msg("sync-check.py SURFACE DRIFT case (Inv 62)", msg)

    # Test 4: session-init @-import
    tmp3 = build_tmproot()
    tmproots.append(tmp3)
    with open(os.path.join(tmp3, "CLAUDE.md"), "w") as f:
        f.write("# Rabbit Workflow — test header\n\n@.claude/features/policy/philosophy.md\n@.claude/features/policy/spec-rules.md\n@.claude/features/policy/coding-rules.md\n")
    # BUG-39: Python-only stack — no .sh stubs.

    env = {**os.environ, "RABBIT_ROOT": tmp3}
    res = subprocess.run([sys.executable, SESSION_INIT], env=env, capture_output=True, text=True)
    msg = extract_sys_msg(res.stdout)
    assert_green_msg("session-init.py @-import case", msg)

    # Test 5: session-init @-import fallback
    tmp3b = build_tmproot()
    tmproots.append(tmp3b)
    os.makedirs(os.path.join(tmp3b, "policy-files"), exist_ok=True)
    with open(os.path.join(tmp3b, "policy-files/p1.md"), "w") as f:
        f.write("# Imported Policy\nHello.\n")
    with open(os.path.join(tmp3b, "CLAUDE.md"), "w") as f:
        f.write("# Rabbit Workflow — test header\n\n@./policy-files/p1.md\n")
    # BUG-39: Python-only stack — no .sh stubs.

    env = {**os.environ, "RABBIT_ROOT": tmp3b}
    res = subprocess.run([sys.executable, SESSION_INIT], env=env, capture_output=True, text=True)
    msg = extract_sys_msg(res.stdout)
    assert_green_msg("session-init.py @-import fallback case", msg)

    # Test 6: refresh inline
    tmp4 = build_tmproot()
    tmproots.append(tmp4)
    # BUG-80: inline rabbit-policy-start/end detection removed from
    # refresh.py. Use @-imports instead (the supported source of truth).
    with open(os.path.join(tmp4, "CLAUDE.md"), "w") as f:
        f.write(
            "# Rabbit Workflow — test header\n\n"
            "@.claude/features/policy/philosophy.md\n"
            "@.claude/features/policy/spec-rules.md\n"
            "@.claude/features/policy/coding-rules.md\n"
        )
    THRESHOLD = "5"
    with open(os.path.join(tmp4, ".rabbit-prompt-counter"), "w") as f:
        f.write(THRESHOLD + "\n")

    env = {**os.environ, "RABBIT_ROOT": tmp4, "RABBIT_REFRESH_EVERY": THRESHOLD}
    res = subprocess.run([sys.executable, REFRESH_HOOK], env=env, capture_output=True, text=True)
    msg = extract_sys_msg(res.stdout)
    assert_green_msg("refresh.py @-import case", msg)

    # Test 7: refresh @-import fallback
    tmp4b = build_tmproot()
    tmproots.append(tmp4b)
    os.makedirs(os.path.join(tmp4b, "policy-files"), exist_ok=True)
    with open(os.path.join(tmp4b, "policy-files/p1.md"), "w") as f:
        f.write("# Imported Policy\nHello.\n")
    with open(os.path.join(tmp4b, "CLAUDE.md"), "w") as f:
        f.write("# Rabbit Workflow — test header\n\n@./policy-files/p1.md\n")
    with open(os.path.join(tmp4b, ".rabbit-prompt-counter"), "w") as f:
        f.write(THRESHOLD + "\n")

    env = {**os.environ, "RABBIT_ROOT": tmp4b, "RABBIT_REFRESH_EVERY": THRESHOLD}
    res = subprocess.run([sys.executable, REFRESH_HOOK], env=env, capture_output=True, text=True)
    msg = extract_sys_msg(res.stdout)
    assert_green_msg("refresh.py @-import fallback case", msg)

    # Test 8: drift8 must be RED
    tmp_d8 = build_tmproot()
    tmproots.append(tmp_d8)
    with open(os.path.join(tmp_d8, "CLAUDE.md"), "w") as f:
        f.write("STALE CONTENT\n")
    msg = extract_sys_msg(run_sync(tmp_d8))
    assert_red_msg("sync-check.py DRIFT case must be RED (alert)", msg)
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
