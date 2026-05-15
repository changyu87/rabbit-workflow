#!/usr/bin/env python3
"""Tests RABBIT-CAGE-21 plugin-change alert (.rabbit-skills-updated marker model)."""
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


def make_clean_repo():
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", d, "checkout", "-q", "-b", "main"], capture_output=True)

    os.makedirs(os.path.join(d, ".claude/features/rabbit-cage/scripts"), exist_ok=True)
    os.makedirs(os.path.join(d, ".claude/features/policy"), exist_ok=True)

    for fname, content in [
        ("philosophy.md", "# Philosophy\nMachine First.\n"),
        ("spec-rules.md", "# Spec Rules\nSpec.\n"),
        ("coding-rules.md", "# Coding Rules\nCode.\n"),
    ]:
        with open(os.path.join(d, ".claude/features/policy", fname), "w") as f:
            f.write(content)

    with open(os.path.join(d, ".claude/features/rabbit-cage/policy-header.json"), "w") as f:
        json.dump({"header": "# Rabbit Workflow — test header"}, f)

    for fname in ("generate-claude-md.py", "generate-claude-md-header.py"):
        shutil.copy(
            os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts", fname),
            os.path.join(d, ".claude/features/rabbit-cage/scripts", fname),
        )

    with open(os.path.join(d, ".claude/features/registry.json"), "w") as f:
        json.dump({"schema_version": "1.0.0", "features": {}}, f)

    env = {**os.environ, "RABBIT_ROOT": d}
    result = subprocess.run(
        [sys.executable, os.path.join(d, ".claude/features/rabbit-cage/scripts/generate-claude-md.py")],
        env=env, capture_output=True, text=True,
    )
    with open(os.path.join(d, "CLAUDE.md"), "w") as f:
        f.write(result.stdout.rstrip("\n") + "\n")

    subprocess.run(["git", "-C", d, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "init"], check=True, capture_output=True)
    return d


def run_sync(tmproot):
    env = {**os.environ, "RABBIT_ROOT": tmproot, "RABBIT_SYNC_EVERY": "1"}
    result = subprocess.run([sys.executable, SYNC_CHECK], env=env, capture_output=True, text=True)
    return result.stdout


print("test-RABBIT-CAGE-21-plugin-change-alert.py")
print()

tmproot = make_clean_repo()
tmproot2 = None

try:
    print("=== t1: .rabbit-skills-updated exists → [rabbit] notification emitted ===")
    with open(os.path.join(tmproot, ".rabbit-skills-updated"), "w") as f:
        f.write("rabbit-bug\n")
    t1_output = run_sync(tmproot)
    t1_msg = extract_sys_msg(t1_output)

    if "[rabbit]" in t1_msg:
        ok("systemMessage contains '[rabbit]'")
    else:
        fail_t(f"systemMessage does NOT contain '[rabbit]' (actual: {t1_msg!r})")

    print("=== t2: notification contains the skill name ===")
    if "rabbit-bug" in t1_msg:
        ok("systemMessage contains 'rabbit-bug'")
    else:
        fail_t(f"systemMessage does NOT contain skill name 'rabbit-bug' (actual: {t1_msg!r})")

    print("=== t3: notification says 'next invocation' ===")
    if "next invocation" in t1_msg:
        ok("systemMessage contains 'next invocation'")
    else:
        fail_t(f"systemMessage does NOT say 'next invocation' (actual: {t1_msg!r})")

    print("=== t4: notification is green (ANSI invariant 18) ===")
    if "\x1b[32m" in t1_msg and "\x1b[0m" in t1_msg:
        ok("notification is green (ANSI \\x1b[32m)")
    else:
        fail_t(f"notification is NOT green (actual: {t1_msg!r})")

    print("=== t5: .rabbit-skills-updated deleted after notification (self-clearing) ===")
    if os.path.isfile(os.path.join(tmproot, ".rabbit-skills-updated")):
        fail_t(".rabbit-skills-updated still exists after sync-check — must be self-clearing")
    else:
        ok(".rabbit-skills-updated deleted by sync-check")

    print("=== t6: second sync-check run → silent (marker already consumed) ===")
    t6_output = run_sync(tmproot)
    t6_msg = extract_sys_msg(t6_output)
    if any(s in t6_msg for s in ("Skills updated", "rabbit-bug", "next invocation")):
        fail_t("notification fired again on second run — must be one-time only")
    else:
        ok("no notification on second run (self-clearing confirmed)")

    print("=== t7: .rabbit-skills-updated absent → no notification ===")
    tmproot2 = make_clean_repo()
    p = os.path.join(tmproot2, ".rabbit-skills-updated")
    if os.path.isfile(p):
        os.remove(p)
    t7_output = run_sync(tmproot2)
    t7_msg = extract_sys_msg(t7_output)
    if any(s in t7_msg for s in ("Skills updated", "next invocation")):
        fail_t("notification fired when .rabbit-skills-updated was absent (false positive)")
    else:
        ok("no notification when .rabbit-skills-updated is absent")

    print("=== t8: sync-check.py does NOT reference .rabbit-plugins-stale ===")
    with open(SYNC_CHECK) as f:
        sc_src = f.read()
    if ".rabbit-plugins-stale" in sc_src:
        fail_t("sync-check.py still references .rabbit-plugins-stale — must be fully removed")
    else:
        ok("sync-check.py has no .rabbit-plugins-stale reference")

    print("=== t9: sync-check.py emits at most one JSON object (single-JSON invariant) ===")
    with open(os.path.join(tmproot, ".rabbit-skills-updated"), "w") as f:
        f.write("rabbit-cage\n")
    t9_output = run_sync(tmproot)

    data = t9_output.strip()
    count = 0
    if not data:
        count = 0
    else:
        try:
            json.loads(data)
            count = 1
        except Exception:
            decoder = json.JSONDecoder()
            idx = 0
            while idx < len(data):
                rest = data[idx:].lstrip()
                if not rest:
                    break
                try:
                    _, end = decoder.raw_decode(rest)
                    count += 1
                    idx += (len(data) - len(data[idx:])) + end
                except Exception:
                    break
    if count in (0, 1):
        ok(f"at most one JSON object emitted (count={count})")
    else:
        fail_t(f"more than one JSON object emitted (count={count}) — violates single-JSON invariant")

    print("=== t10: multiple skill names shown comma-separated ===")
    with open(os.path.join(tmproot, ".rabbit-skills-updated"), "w") as f:
        f.write("rabbit-bug\nrabbit-cage\n")
    t10_output = run_sync(tmproot)
    t10_msg = extract_sys_msg(t10_output)
    if "rabbit-bug" in t10_msg and "rabbit-cage" in t10_msg:
        ok("both skill names appear in message")
    else:
        fail_t(f"not all skill names appear in message (actual: {t10_msg!r})")
finally:
    shutil.rmtree(tmproot, ignore_errors=True)
    if tmproot2:
        shutil.rmtree(tmproot2, ignore_errors=True)

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
