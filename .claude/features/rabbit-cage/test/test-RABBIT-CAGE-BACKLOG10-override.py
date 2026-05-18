#!/usr/bin/env python3
"""Tests scope-guard override feature (RABBIT-CAGE-BACKLOG-10)."""
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
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")
SYNC_CHECK = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/sync-check.py")
GITIGNORE = os.path.join(REPO_ROOT, ".gitignore")

failures = 0
total = 0
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


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


def run_scope_guard(input_json):
    result = subprocess.run([sys.executable, SCOPE_GUARD], input=input_json,
                            capture_output=True, text=True)
    return result.returncode


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

    # BUG-39: Python-only stack — no .sh stubs. The generate-skills-dir step
    # is now driven entirely by build.py + build-contract.json; no separate
    # generate-skills-dir.* script exists or is invoked here.

    env = {**os.environ, "RABBIT_ROOT": tmproot}
    result = subprocess.run([sys.executable, os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
                            env=env, capture_output=True, text=True)
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write(result.stdout.rstrip("\n") + "\n")
    return tmproot


print("test-RABBIT-CAGE-BACKLOG10-override.py")
print()
print("=== GITIGNORE: both override markers must be listed ===")

gitignore = read(GITIGNORE)
gi_lines = [line.strip() for line in gitignore.splitlines()]

# t1
if ".rabbit-scope-override" in gi_lines:
    ok(".rabbit-scope-override is listed in .gitignore")
else:
    fail_t(".rabbit-scope-override is NOT listed in .gitignore")

# t2
if ".rabbit-scope-override-used" in gi_lines:
    ok(".rabbit-scope-override-used is listed in .gitignore")
else:
    fail_t(".rabbit-scope-override-used is NOT listed in .gitignore")

print()
print("=== SCOPE-GUARD: session override ===")

MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-active")
FEATURE_JSON = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/feature.json")
OVERRIDE_MARKER = os.path.join(REPO_ROOT, ".rabbit-scope-override")
OVERRIDE_USED = os.path.join(REPO_ROOT, ".rabbit-scope-override-used")

marker_existed = os.path.isfile(MARKER)
marker_backup = read(MARKER) if marker_existed else ""
feature_json_backup = read(FEATURE_JSON)

# Save and remove existing override markers
override_marker_existed = os.path.isfile(OVERRIDE_MARKER)
override_marker_backup = read(OVERRIDE_MARKER) if override_marker_existed else ""
override_used_existed = os.path.isfile(OVERRIDE_USED)

if os.path.isfile(OVERRIDE_MARKER):
    os.remove(OVERRIDE_MARKER)
if os.path.isfile(OVERRIDE_USED):
    os.remove(OVERRIDE_USED)

with open(MARKER, "w") as f:
    f.write("rabbit-cage")

d = json.loads(feature_json_backup)
d["tdd_state"] = "test-green"
with open(FEATURE_JSON, "w") as f:
    json.dump(d, f, indent=2)

# Pre-check: deny without override
t3_pre_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t3_pre_exit = run_scope_guard(t3_pre_input)

with open(OVERRIDE_MARKER, "w") as f:
    f.write("session")

# t3
t3_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t3_exit = run_scope_guard(t3_input)

if t3_exit == 0 and t3_pre_exit == 2:
    ok("scope-guard exits 0 (ALLOW) when .rabbit-scope-override=session (overrides test-green deny)")
elif t3_pre_exit != 2:
    fail_t(f"pre-condition failed: scope-guard did not deny test-green write (got {t3_pre_exit}, expected 2) — test setup error")
else:
    fail_t(f"scope-guard exited {t3_exit} (expected 0/ALLOW) with .rabbit-scope-override=session — override not implemented")

# t4
sg_src = read(SCOPE_GUARD)
if ".rabbit-scope-override" in sg_src:
    ok("scope-guard.py references .rabbit-scope-override — override logic is present")
else:
    fail_t("scope-guard.py does NOT reference .rabbit-scope-override — override logic not implemented")

if os.path.isfile(OVERRIDE_MARKER):
    os.remove(OVERRIDE_MARKER)

print()
print("=== SCOPE-GUARD: one-time override ===")

with open(OVERRIDE_MARKER, "w") as f:
    f.write("one-time")
if os.path.isfile(OVERRIDE_USED):
    os.remove(OVERRIDE_USED)

t5_input = '{"tool_name":"Write","tool_input":{"file_path":".claude/features/rabbit-cage/somefile.txt"}}'
t5_exit = run_scope_guard(t5_input)

# t5
if t5_exit == 0:
    ok("scope-guard exits 0 (ALLOW) when .rabbit-scope-override=one-time (overrides test-green deny)")
else:
    fail_t(f"scope-guard exited {t5_exit} (expected 0/ALLOW) with .rabbit-scope-override=one-time — override not implemented")

# t6
if not os.path.isfile(OVERRIDE_MARKER):
    ok(".rabbit-scope-override is deleted after one-time override ALLOW")
else:
    fail_t(".rabbit-scope-override still exists after one-time override — it should have been deleted")

# t7
if os.path.isfile(OVERRIDE_USED):
    ok(".rabbit-scope-override-used is created after one-time override ALLOW")
else:
    fail_t(".rabbit-scope-override-used was NOT created after one-time override — used-flag not implemented")

# Restore feature.json and markers
with open(FEATURE_JSON, "w") as f:
    f.write(feature_json_backup)
if marker_existed:
    with open(MARKER, "w") as f:
        f.write(marker_backup)
else:
    if os.path.isfile(MARKER):
        os.remove(MARKER)
if os.path.isfile(OVERRIDE_MARKER):
    os.remove(OVERRIDE_MARKER)
if os.path.isfile(OVERRIDE_USED):
    os.remove(OVERRIDE_USED)
# Restore original override markers if existed
if override_marker_existed:
    with open(OVERRIDE_MARKER, "w") as f:
        f.write(override_marker_backup)
if override_used_existed:
    open(OVERRIDE_USED, "a").close()

print()
print("=== RBT-SYNC-CHECK: override alert messages ===")

tmproots = []
try:
    # t8
    tmproot8 = build_tmproot_clean()
    tmproots.append(tmproot8)
    with open(os.path.join(tmproot8, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    env = {**os.environ, "RABBIT_ROOT": tmproot8, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    t8_msg = extract_sys_msg(res.stdout)
    if RED in t8_msg and RESET in t8_msg:
        ok("sync-check.py emits red ANSI alert when .rabbit-scope-override=session")
    else:
        fail_t(f"sync-check.py did NOT emit red ANSI alert for session override (msg: {t8_msg!r})")

    # t9
    tmproot9 = build_tmproot_clean()
    tmproots.append(tmproot9)
    open(os.path.join(tmproot9, ".rabbit-scope-override-used"), "a").close()
    env = {**os.environ, "RABBIT_ROOT": tmproot9, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    t9_msg = extract_sys_msg(res.stdout)
    if RED in t9_msg and RESET in t9_msg:
        ok("sync-check.py emits red ANSI alert when .rabbit-scope-override-used exists")
    else:
        fail_t(f"sync-check.py did NOT emit red ANSI alert for override-used flag (msg: {t9_msg!r})")

    # t10
    if not os.path.isfile(os.path.join(tmproot9, ".rabbit-scope-override-used")):
        ok(".rabbit-scope-override-used is deleted by sync-check.py after alert (one-shot)")
    else:
        fail_t(".rabbit-scope-override-used still exists after sync-check.py ran — one-shot deletion not implemented")
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
