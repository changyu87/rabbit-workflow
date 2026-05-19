#!/usr/bin/env python3
"""BACKLOG-20 / Inv 80 FULL E2E test for leading-newline aggregation.

The aggregated systemMessage emitted by sync-check.py and session-init.py
MUST begin with exactly one '\\n' so the [🐇 rabbit 🐇] banner block starts
on its own line rather than inline with 'Stop says:' / 'SessionStart says:'
chrome. Zero-condition case is unchanged (no JSON at all).

Three full e2e cases:
  (a) sync-check.py with .rabbit-human-approval-bypass marker active.
  (b) session-init.py on main branch with CLAUDE.md @-imports.
  (c) sync-check.py zero-condition case → empty stdout.
"""
import json
import os
import shutil
import subprocess
import sys

from test_helpers import REPO_ROOT, make_git_repo, run_sync

SESSION_INIT = os.path.join(
    REPO_ROOT, ".claude/features/rabbit-cage/hooks/session-init.py"
)
BRAND = "[🐇 rabbit 🐇]"

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


def run_session_init(tmproot):
    env = {**os.environ, "RABBIT_ROOT": tmproot}
    res = subprocess.run(
        [sys.executable, SESSION_INIT],
        env=env, capture_output=True, text=True,
    )
    return res.stdout


print("test-RABBIT-CAGE-BACKLOG-20-leading-newline.py")
print("FULL E2E: aggregated systemMessage MUST begin with exactly one '\\n'")
print()

tmproots = []
try:
    # ---- (a) sync-check.py with human-approval-bypass marker ----
    print("=== t-a: sync-check.py with human-approval-bypass marker ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    open(os.path.join(tmproot, ".rabbit-human-approval-bypass"), "a").close()

    out = run_sync(tmproot)
    if not out.strip():
        fail_t(f"sync-check.py emitted no JSON despite marker present: {out!r}")
    else:
        try:
            obj = json.loads(out.strip())
        except Exception as e:
            fail_t(f"sync-check.py output does not parse as JSON: {e}; raw={out!r}")
            obj = {}
        msg = obj.get("systemMessage", "")
        if msg.startswith("\n"):
            ok("sync-check systemMessage starts with '\\n'")
        else:
            fail_t(
                f"sync-check systemMessage does NOT start with '\\n'; "
                f"first 40 chars: {msg[:40]!r}"
            )
        if msg.startswith("\n\n"):
            fail_t(
                f"sync-check systemMessage starts with DOUBLE '\\n\\n' "
                f"(expected exactly one leading newline); first 40 chars: {msg[:40]!r}"
            )
        else:
            ok("sync-check systemMessage has exactly one leading '\\n' (not double)")
        # The content immediately after the leading '\n' must be a rabbit
        # banner line — i.e., it must contain the brand within the first
        # rendered line (which is wrapped in ANSI color codes).
        first_line = msg[1:].split("\n", 1)[0] if msg.startswith("\n") else ""
        if BRAND in first_line:
            ok(f"sync-check first line after leading '\\n' contains brand `{BRAND}`")
        else:
            fail_t(
                f"sync-check first line after leading '\\n' missing brand `{BRAND}`; "
                f"first line: {first_line!r}"
            )

    # ---- (b) session-init.py on main branch with @-imports ----
    print()
    print("=== t-b: session-init.py on main with CLAUDE.md @-imports ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    claude_md = os.path.join(tmproot, "CLAUDE.md")
    with open(claude_md, "a") as f:
        f.write("\n@.claude/features/policy/philosophy.md\n")
        f.write("@.claude/features/policy/spec-rules.md\n")
        f.write("@.claude/features/policy/coding-rules.md\n")

    out = run_session_init(tmproot)
    if not out.strip():
        fail_t(f"session-init.py emitted no JSON: {out!r}")
    else:
        try:
            obj = json.loads(out.strip())
        except Exception as e:
            fail_t(f"session-init.py output does not parse as JSON: {e}; raw={out!r}")
            obj = {}
        msg = obj.get("systemMessage", "")
        if msg.startswith("\n"):
            ok("session-init systemMessage starts with '\\n'")
        else:
            fail_t(
                f"session-init systemMessage does NOT start with '\\n'; "
                f"first 40 chars: {msg[:40]!r}"
            )
        if msg.startswith("\n\n"):
            fail_t(
                f"session-init systemMessage starts with DOUBLE '\\n\\n' "
                f"(expected exactly one leading newline); first 40 chars: {msg[:40]!r}"
            )
        else:
            ok("session-init systemMessage has exactly one leading '\\n' (not double)")
        first_line = msg[1:].split("\n", 1)[0] if msg.startswith("\n") else ""
        if BRAND in first_line:
            ok(f"session-init first line after leading '\\n' contains brand `{BRAND}`")
        else:
            fail_t(
                f"session-init first line after leading '\\n' missing brand `{BRAND}`; "
                f"first line: {first_line!r}"
            )

    # ---- (c) zero-condition sync-check.py ----
    print()
    print("=== t-c: sync-check.py zero-condition case → empty stdout (no JSON) ===")
    tmproot = make_git_repo()
    tmproots.append(tmproot)
    out = run_sync(tmproot)
    if out.strip() == "":
        ok("zero-condition sync-check emits empty stdout (no JSON)")
    else:
        fail_t(f"zero-condition sync-check emitted unexpected output: {out!r}")

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
