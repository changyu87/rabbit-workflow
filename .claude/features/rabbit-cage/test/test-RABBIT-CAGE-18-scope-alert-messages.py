#!/usr/bin/env python3
"""Tests that sync-check.py emits distinct messages for _alert=session vs _alert=used."""
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


def extract_sys_msg(output):
    try:
        d = json.loads(output)
        return d.get("systemMessage", "")
    except Exception:
        return ""


def build_tmproot_clean():
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

    skills_path = os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-skills-dir.sh")
    with open(skills_path, "w") as f:
        f.write("#!/usr/bin/env bash\nexit 0\n")
    os.chmod(skills_path, 0o755)

    env = {**os.environ, "RABBIT_ROOT": tmproot}
    result = subprocess.run(
        [sys.executable, os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
        env=env, capture_output=True, text=True,
    )
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write(result.stdout.rstrip("\n") + "\n")

    return tmproot


print("test-RABBIT-CAGE-18-scope-alert-messages.py")
print()

# ---- t1: session message ----
print("=== t1: _alert=session message contains 'SCOPE GUARD OFF (session override active)' ===")
tmproot_session = build_tmproot_clean()
with open(os.path.join(tmproot_session, ".rabbit-scope-override"), "w") as f:
    f.write("session")

env = {**os.environ, "RABBIT_ROOT": tmproot_session, "RABBIT_SYNC_EVERY": "1"}
result = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
t1_msg = extract_sys_msg(result.stdout)

EXPECTED_SESSION = "SCOPE GUARD OFF (session override active)"
if EXPECTED_SESSION in t1_msg:
    ok(f"session alert contains '{EXPECTED_SESSION}'")
else:
    fail_t(f"session alert does NOT contain '{EXPECTED_SESSION}' (actual: {t1_msg!r})")

# ---- t2: used message ----
print("=== t2: _alert=used message contains 'SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed)' ===")
tmproot_used = build_tmproot_clean()
open(os.path.join(tmproot_used, ".rabbit-scope-override-used"), "a").close()

env = {**os.environ, "RABBIT_ROOT": tmproot_used, "RABBIT_SYNC_EVERY": "1"}
result = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
t2_msg = extract_sys_msg(result.stdout)

EXPECTED_USED = "SCOPE GUARD BYPASSED (one-time override consumed — guard re-armed)"
if EXPECTED_USED in t2_msg:
    ok(f"used alert contains '{EXPECTED_USED}'")
else:
    fail_t(f"used alert does NOT contain '{EXPECTED_USED}' (actual: {t2_msg!r})")

# ---- t3: distinct ----
print("=== t3: session and used messages are distinct ===")
if t1_msg != t2_msg:
    ok("session and used alert messages are distinct")
else:
    fail_t("session and used alert messages are identical — they must be distinct")

# ---- t4: red ANSI session ----
print("=== t4: session alert is still red (regression guard) ===")
RED = "\x1b[31m"
RESET = "\x1b[0m"
if RED in t1_msg and RESET in t1_msg:
    ok("session alert is red (ANSI)")
else:
    fail_t("session alert is NOT red — regression in color convention")

# ---- t5: red ANSI used ----
print("=== t5: used alert is red ===")
if RED in t2_msg and RESET in t2_msg:
    ok("used alert is red (ANSI)")
else:
    fail_t("used alert is NOT red — must use red ANSI code per spec")

shutil.rmtree(tmproot_session, ignore_errors=True)
shutil.rmtree(tmproot_used, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
