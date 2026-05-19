#!/usr/bin/env python3
"""BACKLOG-19 / Inv 78: session-init.py welcome banner + per-file sublines.

Full e2e: invoke session-init.py on a temp repo on main branch with the
three standard @-imports (philosophy.md, spec-rules.md, coding-rules.md).
Parse the emitted JSON systemMessage. Assert:
  - Welcome banner (brand `[🐇 rabbit 🐇]`) is present.
  - The three per-file sub-lines with the exact one-liner descriptions are
    present.
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_helpers import REPO_ROOT, make_git_repo

SESSION_INIT = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py")
BRAND = "[🐇 rabbit 🐇]"

EXPECTED_SUBLINES = [
    f"{BRAND} philosophy.md    — machine-first · bounded scope · designed deprecation",
    f"{BRAND} spec-rules.md    — determinism first; schema contracts; lifecycle ownership",
    f"{BRAND} coding-rules.md  — think first; simplicity; surgical edits; goal-driven TDD",
]

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


print("test-RABBIT-CAGE-BACKLOG-19-welcome-sublines.py")
print()

tmproots = []
try:
    tmproot = make_git_repo()
    tmproots.append(tmproot)

    # Make sure CLAUDE.md has the three default @-imports (the make_git_repo
    # builder uses the generator which already emits them; ensure they're present).
    claude_md = os.path.join(tmproot, "CLAUDE.md")
    text = open(claude_md).read()
    needed = [
        "@.claude/features/policy/philosophy.md",
        "@.claude/features/policy/spec-rules.md",
        "@.claude/features/policy/coding-rules.md",
    ]
    add = "\n".join(s for s in needed if s not in text)
    if add:
        with open(claude_md, "a") as f:
            f.write("\n" + add + "\n")

    env = {**os.environ, "RABBIT_ROOT": tmproot}
    res = subprocess.run(
        [sys.executable, SESSION_INIT], env=env, capture_output=True, text=True,
    )
    out = res.stdout.strip()
    try:
        obj = json.loads(out)
    except Exception as e:
        fail_t(f"session-init.py did not emit a single parseable JSON object: {e}; raw={out!r}")
        obj = {}

    msg = obj.get("systemMessage", "")
    if BRAND in msg:
        ok(f"systemMessage contains the new brand `{BRAND}`")
    else:
        fail_t(f"systemMessage missing brand `{BRAND}`; got: {msg!r}")

    for expected in EXPECTED_SUBLINES:
        if expected in msg:
            ok(f"systemMessage contains expected subline `{expected}`")
        else:
            fail_t(f"systemMessage missing expected subline `{expected}`; got: {msg!r}")
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
