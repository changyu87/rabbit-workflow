#!/usr/bin/env python3
"""BACKLOG-18 FULL E2E test for session-init.py single-JSON emission (Inv 75).

Builds a realistic temp repo with real CLAUDE.md and @-import files on the
'main' branch; invokes session-init.py as a subprocess; asserts:

  - Exactly ONE JSON object is emitted (no second emission).
  - systemMessage contains both R1 line and policy line joined by '\\n'.
  - additionalContext is present and non-empty.
  - On a non-main branch with no @-imports, no JSON is emitted.
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
print("FULL E2E: session-init.py single-JSON emission")
print()

tmproots = []
try:
    # ---- t1: on main with real CLAUDE.md + @-imports → single JSON ----
    print("=== t1: on main with real CLAUDE.md and @-imports → ONE JSON object ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    # Append @-imports so policy injection has content.
    claude_md = os.path.join(tmproot, "CLAUDE.md")
    with open(claude_md, "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")
        f.write("@.claude/features/policy/spec-rules.md\n")
        f.write("@.claude/features/policy/coding-rules.md\n")

    out = run_hook(tmproot)
    n = count_json_objects(out)
    if n == 1:
        ok("exactly ONE JSON object emitted (Inv 75)")
    else:
        fail_t(f"expected 1 JSON object, got {n}; raw: {out!r}")

    try:
        obj = json.loads(out.strip())
        ok("emitted output parses as single JSON object")
    except Exception as e:
        fail_t(f"emitted output does NOT parse as a single JSON object: {e}")
        obj = {}

    msg = obj.get("systemMessage", "")
    if "R1: created branch session/" in msg:
        ok("R1 line present in aggregated systemMessage")
    else:
        fail_t(f"R1 line missing: {msg!r}")
    # BACKLOG-19: welcome banner replaces "Policy injected".
    if "Welcome" in msg:
        ok("welcome banner present in aggregated systemMessage")
    else:
        fail_t(f"welcome banner missing: {msg!r}")

    idx_r1 = msg.find("R1: created branch")
    idx_pol = msg.find("Welcome")
    if 0 <= idx_r1 < idx_pol:
        ok("R1 line appears before welcome banner (per Inv 75 ordering)")
    else:
        fail_t(f"ordering wrong; r1={idx_r1} welcome={idx_pol}")

    ac = obj.get("additionalContext", "")
    if ac and len(ac) > 0:
        ok("additionalContext present and non-empty")
    else:
        fail_t(f"additionalContext missing or empty: ac={ac!r}")

    if "Machine First" in ac:
        ok("additionalContext carries actual policy text (philosophy.md content)")
    else:
        fail_t(f"additionalContext does not contain expected policy text; ac[:200]={ac[:200]!r}")

    # ---- t2: off-main with no @-imports → empty stdout ----
    print()
    print("=== t2: off-main with no @-imports → empty stdout ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    subprocess.run(
        ["git", "-C", tmproot, "checkout", "-q", "-b", "feature/test"], capture_output=True,
    )
    # Replace CLAUDE.md with one that has NO @-imports
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write("# CLAUDE.md\nNo imports here.\n")

    out = run_hook(tmproot)
    if out.strip() == "":
        ok("no JSON emitted when no condition applies")
    else:
        fail_t(f"unexpected output for zero-condition: {out!r}")

    # ---- t3: off-main WITH @-imports → ONE JSON, only policy line ----
    print()
    print("=== t3: off-main + @-imports → ONE JSON with only policy line ===")
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
        if "R1: created branch" not in msg:
            ok("R1 line correctly absent on non-main branch")
        else:
            fail_t(f"R1 line should be absent on feature branch: {msg!r}")
        if "Welcome" in msg:
            ok("welcome banner present")
        else:
            fail_t(f"welcome banner missing: {msg!r}")

    # ---- t4: on main but no @-imports → ONE JSON with only R1 line ----
    print()
    print("=== t4: on main + no @-imports → ONE JSON with only R1 line ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    with open(os.path.join(tmproot, "CLAUDE.md"), "w") as f:
        f.write("# CLAUDE.md\nNo imports here.\n")
    # Commit so working tree is clean for checkout
    subprocess.run(["git", "-C", tmproot, "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", tmproot, "commit", "-q", "-m", "remove imports"],
        check=True, capture_output=True,
    )
    out = run_hook(tmproot)
    n = count_json_objects(out)
    if n == 1:
        ok("exactly ONE JSON for R1-only")
    else:
        fail_t(f"expected 1 JSON, got {n}; raw: {out!r}")
    if n == 1:
        obj = json.loads(out.strip())
        msg = obj.get("systemMessage", "")
        if "R1: created branch" in msg:
            ok("R1 line present")
        else:
            fail_t(f"R1 line missing: {msg!r}")
        if "Welcome" not in msg:
            ok("welcome banner absent when no @-imports")
        else:
            fail_t(f"welcome banner should be absent: {msg!r}")
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
