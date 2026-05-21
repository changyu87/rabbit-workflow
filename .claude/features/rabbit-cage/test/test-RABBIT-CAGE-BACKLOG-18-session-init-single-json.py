#!/usr/bin/env python3
"""BACKLOG-18 FULL E2E test for session-init.py single-JSON emission (Inv 85).

After spec v3.12.0, R1 branch enforcement is removed (Inv 41); policy injection
is the sole pending condition for session-init.py.

Builds a realistic temp repo with real CLAUDE.md and @-import files; invokes
session-init.py as a subprocess; asserts:

  - Exactly ONE JSON object is emitted when @-imports exist.
  - systemMessage contains the welcome banner; no R1 text appears.
  - additionalContext is present and non-empty with expanded policy text.
  - With no @-imports, no JSON is emitted (regardless of branch).
"""
import json
import os
import shutil
import subprocess
import sys

from test_helpers import REPO_ROOT, make_git_repo

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


def count_json_objects(data):
    data = data.strip()
    if not data:
        return 0
    decoder = json.JSONDecoder()
    idx = 0
    count = 0
    while idx < len(data):
        rest = data[idx:].lstrip()
        if not rest:
            break
        try:
            _, end = decoder.raw_decode(rest)
            count += 1
            consumed = (len(data) - len(data[idx:])) + end
            idx = consumed
        except Exception:
            break
    return count


def run_hook(tmproot):
    env = {**os.environ, "RABBIT_ROOT": tmproot}
    res = subprocess.run([sys.executable, HOOK], env=env, capture_output=True, text=True)
    return res.stdout


print("test-RABBIT-CAGE-BACKLOG-18-session-init-single-json.py")
print("FULL E2E: session-init.py single-JSON emission (policy-only after Inv 41)")
print()

tmproots = []
try:
    # ---- t1: on main with real CLAUDE.md + @-imports → ONE JSON, policy only ----
    print("=== t1: on main + @-imports → ONE JSON object (policy only, no R1) ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    claude_md = os.path.join(tmproot, "CLAUDE.md")
    with open(claude_md, "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")
        f.write("@.claude/features/policy/spec-rules.md\n")
        f.write("@.claude/features/policy/coding-rules.md\n")

    out = run_hook(tmproot)
    n = count_json_objects(out)
    if n == 1:
        ok("exactly ONE JSON object emitted (Inv 85)")
    else:
        fail_t(f"expected 1 JSON object, got {n}; raw: {out!r}")

    try:
        obj = json.loads(out.strip())
        ok("emitted output parses as single JSON object")
    except Exception as e:
        fail_t(f"emitted output does NOT parse as a single JSON object: {e}")
        obj = {}

    msg = obj.get("systemMessage", "")
    if "R1" not in msg and "session/" not in msg:
        ok("R1/session-branch text absent from systemMessage (Inv 41)")
    else:
        fail_t(f"R1/session-branch text present: {msg!r}")
    if "Welcome" in msg:
        ok("welcome banner present in systemMessage")
    else:
        fail_t(f"welcome banner missing: {msg!r}")

    ac = obj.get("additionalContext", "")
    if ac and len(ac) > 0:
        ok("additionalContext present and non-empty")
    else:
        fail_t(f"additionalContext missing or empty: ac={ac!r}")

    if "Machine First" in ac:
        ok("additionalContext carries actual policy text (philosophy.md content)")
    else:
        fail_t(f"additionalContext does not contain expected policy text; ac[:200]={ac[:200]!r}")

    # Sanity: branch on tmp repo was 'main' before invocation; assert it's
    # still 'main' after (Inv 41 — no auto-switch).
    branch = subprocess.run(
        ["git", "-C", tmproot, "branch", "--show-current"],
        capture_output=True, text=True,
    ).stdout.strip()
    if branch == "main":
        ok("on-main branch unchanged after session-init invocation (Inv 41)")
    else:
        fail_t(f"branch unexpectedly changed to '{branch}' (Inv 41 violation)")

    # ---- t2: off-main with no @-imports → empty stdout ----
    print()
    print("=== t2: off-main with no @-imports → empty stdout ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    subprocess.run(
        ["git", "-C", tmproot, "checkout", "-q", "-b", "feature/test"], capture_output=True,
    )
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write("# CLAUDE.md\nNo imports here.\n")

    out = run_hook(tmproot)
    if out.strip() == "":
        ok("no JSON emitted when no condition applies")
    else:
        fail_t(f"unexpected output for zero-condition: {out!r}")

    # ---- t3: off-main WITH @-imports → ONE JSON, policy only ----
    print()
    print("=== t3: off-main + @-imports → ONE JSON with policy line only ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    subprocess.run(
        ["git", "-C", tmproot, "checkout", "-q", "-b", "feature/keep"], capture_output=True,
    )
    with open(os.path.join(tmproot, "CLAUDE.md"), "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")

    out = run_hook(tmproot)
    n = count_json_objects(out)
    if n == 1:
        ok("exactly ONE JSON object emitted for policy-only")
    else:
        fail_t(f"expected 1 JSON, got {n}; raw: {out!r}")

    if n == 1:
        obj = json.loads(out.strip())
        msg = obj.get("systemMessage", "")
        if "R1" not in msg and "session/" not in msg:
            ok("R1/session-branch text absent on feature branch")
        else:
            fail_t(f"R1/session-branch text should be absent: {msg!r}")
        if "Welcome" in msg:
            ok("welcome banner present")
        else:
            fail_t(f"welcome banner missing: {msg!r}")

    # ---- t4: on main but no @-imports → NO JSON (R1 no longer emits) ----
    print()
    print("=== t4: on main + no @-imports → no JSON at all (Inv 41) ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write("# CLAUDE.md\nNo imports here.\n")
    subprocess.run(["git", "-C", tmproot, "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", tmproot, "commit", "-q", "-m", "remove imports"],
        check=True, capture_output=True,
    )
    out = run_hook(tmproot)
    if out.strip() == "":
        ok("no JSON emitted on main without @-imports (R1 removed)")
    else:
        fail_t(f"expected empty stdout, got: {out!r}")
    branch = subprocess.run(
        ["git", "-C", tmproot, "branch", "--show-current"],
        capture_output=True, text=True,
    ).stdout.strip()
    if branch == "main":
        ok("branch unchanged at 'main' (Inv 41 — R1 removed)")
    else:
        fail_t(f"branch unexpectedly switched to '{branch}' (Inv 41 violation)")
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
