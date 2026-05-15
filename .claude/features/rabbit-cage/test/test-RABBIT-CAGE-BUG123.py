#!/usr/bin/env python3
"""Tests for three rabbit-cage bugs: BUG-1, BUG-2, BUG-3."""
import importlib.util
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
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")
SCOPE_GUARD_ON = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts/scope-guard-on.py")

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

    env = {**os.environ, "RABBIT_ROOT": tmproot}
    result = subprocess.run([sys.executable, os.path.join(tmproot, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
                            env=env, capture_output=True, text=True)
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write(result.stdout.rstrip("\n") + "\n")
    return tmproot


def source_and_extract(cmd):
    spec = importlib.util.spec_from_file_location("sg", SCOPE_GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return list(m.extract_bash_targets(cmd))


print("test-RABBIT-CAGE-BUG123.py")
print()

# BUG-1
print("=== BUG-1: SCOPE GUARD OFF alert uses literal emoji and box-drawing chars ===")

tmproot_bug1 = build_tmproot_clean()
try:
    with open(os.path.join(tmproot_bug1, ".rabbit-scope-override"), "w") as f:
        f.write("session")

    env = {**os.environ, "RABBIT_ROOT": tmproot_bug1, "RABBIT_SYNC_EVERY": "1"}
    res = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    bug1_msg = extract_sys_msg(res.stdout)

    if "\U0001f513" in bug1_msg:
        ok("BUG-1a: SCOPE GUARD OFF message contains literal 🔓 (U+1F513)")
    else:
        fail_t(f"BUG-1a: SCOPE GUARD OFF message does NOT contain literal 🔓 — got: {bug1_msg!r}")

    if "━" in bug1_msg:
        ok("BUG-1b: SCOPE GUARD OFF message contains literal ━ (U+2501)")
    else:
        fail_t(f"BUG-1b: SCOPE GUARD OFF message does NOT contain literal ━ — got: {bug1_msg!r}")

    if "\xf0" not in bug1_msg and "\xe2" not in bug1_msg:
        ok("BUG-1c: SCOPE GUARD OFF message does NOT contain garbled byte-escape artifacts")
    else:
        fail_t("BUG-1c: SCOPE GUARD OFF message contains garbled byte-escape artifacts — bytes escaped as \\xNN in Python 3 Unicode string")
finally:
    shutil.rmtree(tmproot_bug1, ignore_errors=True)

print()

# BUG-2
print("=== BUG-2: scope-guard-on.py exists and revokes session override ===")

if os.access(SCOPE_GUARD_ON, os.X_OK):
    ok("BUG-2a: scope-guard-on.py exists and is executable")
else:
    fail_t(f"BUG-2a: scope-guard-on.py does NOT exist or is not executable at {SCOPE_GUARD_ON}")

tmpdir_bug2 = tempfile.mkdtemp()
try:
    with open(os.path.join(tmpdir_bug2, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    if os.access(SCOPE_GUARD_ON, os.X_OK):
        env = {**os.environ, "RABBIT_ROOT": tmpdir_bug2}
        subprocess.run([sys.executable, SCOPE_GUARD_ON], env=env, capture_output=True)
        if not os.path.isfile(os.path.join(tmpdir_bug2, ".rabbit-scope-override")):
            ok("BUG-2b: scope-guard-on.py removed .rabbit-scope-override (session override revoked)")
        else:
            fail_t("BUG-2b: scope-guard-on.py did NOT remove .rabbit-scope-override")
    else:
        fail_t("BUG-2b: skipped (scope-guard-on.py not executable)")

    # BUG-2c
    if os.access(SCOPE_GUARD_ON, os.X_OK):
        env = {**os.environ, "RABBIT_ROOT": tmpdir_bug2}
        res = subprocess.run([sys.executable, SCOPE_GUARD_ON], env=env, capture_output=True)
        if res.returncode == 0:
            ok("BUG-2c: scope-guard-on.py exits 0 when no override is active (no-op)")
        else:
            fail_t(f"BUG-2c: scope-guard-on.py exited {res.returncode} when no override active — expected 0")
    else:
        fail_t("BUG-2c: skipped (scope-guard-on.py not executable)")
finally:
    shutil.rmtree(tmpdir_bug2, ignore_errors=True)

# BUG-2d
tmpdir_bug2d = tempfile.mkdtemp()
try:
    with open(os.path.join(tmpdir_bug2d, ".rabbit-scope-override"), "w") as f:
        f.write("one-time")
    if os.access(SCOPE_GUARD_ON, os.X_OK):
        env = {**os.environ, "RABBIT_ROOT": tmpdir_bug2d}
        subprocess.run([sys.executable, SCOPE_GUARD_ON], env=env, capture_output=True)
        if not os.path.isfile(os.path.join(tmpdir_bug2d, ".rabbit-scope-override")):
            ok("BUG-2d: scope-guard-on.py removed .rabbit-scope-override (one-time override revoked)")
        else:
            fail_t("BUG-2d: scope-guard-on.py did NOT remove .rabbit-scope-override for one-time mode")
    else:
        fail_t("BUG-2d: skipped (scope-guard-on.py not executable)")
finally:
    shutil.rmtree(tmpdir_bug2d, ignore_errors=True)

print()

# BUG-3
print("=== BUG-3: extract_bash_targets handles multi-line double-quoted strings ===")

cmd_bug3a = 'gh pr create --title "Test PR" --description "Changes: \\\n-> U+00F0 is the padlock emoji \\\nFix garbled output"'
targets_bug3a = source_and_extract(cmd_bug3a)
joined = "\n".join(targets_bug3a)
if "U+00F0" in joined:
    fail_t("BUG-3a: false positive — 'U+00F0' inside multi-line double-quoted string detected as write target")
elif any(s in joined for s in ("padlock", "garbled", "Changes")):
    fail_t("BUG-3a: false positive — content inside multi-line double-quoted string detected as write target")
else:
    ok("BUG-3a: multi-line double-quoted --description with '-> U+00F0' is NOT a false positive")

cmd_bug3b = 'gh pr create --description "multi \\\nline desc" > /tmp/real_out_bug3b'
targets_bug3b = source_and_extract(cmd_bug3b)
if any("/tmp/real_out_bug3b" in t for t in targets_bug3b):
    ok("BUG-3b: real unquoted redirect after multi-line quoted arg IS detected (no regression)")
else:
    fail_t("BUG-3b: regression — real unquoted redirect '/tmp/real_out_bug3b' was NOT detected")

cmd_bug3c = 'echo "some > /tmp/evil_bug3c here"'
targets_bug3c = source_and_extract(cmd_bug3c)
if any("/tmp/evil_bug3c" in t for t in targets_bug3c):
    fail_t("BUG-3c: false positive — redirect inside single-line double-quoted string detected")
else:
    ok("BUG-3c: redirect inside single-line double-quoted string is NOT a false positive (regression guard)")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
