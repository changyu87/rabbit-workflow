#!/usr/bin/env python3
"""E2E test for Invariant 52: scope-guard default-deny message structure.

Verifies that when scope-guard.py reaches the default-deny path (no scope
marker, no override, no allowlist match), the DENY message printed to
stderr presents three explicit options in a structured form:
  1. SESSION OVERRIDE  — requires explicit in-conversation user confirmation
  2. ONE-TIME OVERRIDE — requires explicit in-conversation user confirmation
  3. USE rabbit-feature-touch (recommended)
And does NOT contain the old terse "Dispatcher must touch
.rabbit-scope-active before calling Agent" rationalization wording.

This is the BUG-1 (TDD-STATE-MACHINE-BUG-1) regression test: the deny
message must force an explicit decision point, not frame override as a
silent procedural next step.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
SCOPE_GUARD = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks/scope-guard.py")

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


def run_scope_guard(payload):
    """Invoke scope-guard.py with a JSON tool payload via stdin.

    Returns (returncode, stderr_text).
    """
    result = subprocess.run(
        [sys.executable, SCOPE_GUARD],
        input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return result.returncode, result.stderr


def temporarily_clear_markers():
    """Clear all scope markers and overrides in repo root; return restore fn."""
    saved = []
    paths = [
        os.path.join(REPO_ROOT, ".rabbit-scope-active"),
        os.path.join(REPO_ROOT, ".rabbit-scope-override"),
        os.path.join(REPO_ROOT, ".rabbit-scope-override-used"),
    ]
    paths.extend(glob.glob(os.path.join(REPO_ROOT, ".rabbit-scope-active-*")))
    for p in paths:
        if os.path.isfile(p):
            with open(p) as f:
                saved.append((p, f.read()))
            os.remove(p)

    def restore():
        for p, content in saved:
            with open(p, "w") as f:
                f.write(content)
    return restore


print("test-scope-guard-deny-message.py")
print()
print("=== Invariant 52: structured three-option default-deny message ===")

restore = temporarily_clear_markers()
try:
    # Target a path inside a feature directory with no scope marker,
    # no override, and not on the allowlist. This forces the
    # default-deny path.
    target = os.path.join(
        REPO_ROOT,
        ".claude/features/rabbit-cage/scripts/__deny_msg_test_target__.txt",
    )
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target, "content": "x"},
    }
    rc, stderr = run_scope_guard(payload)

    # t1: scope-guard must deny (exit 2)
    if rc == 2:
        ok("default-deny path exits 2 (DENY)")
    else:
        fail_t(f"default-deny path exits {rc} (expected 2); stderr={stderr!r}")

    # t2: message must contain literal 'SESSION OVERRIDE'
    if "SESSION OVERRIDE" in stderr:
        ok("DENY message contains literal 'SESSION OVERRIDE'")
    else:
        fail_t(f"DENY message missing 'SESSION OVERRIDE' — got: {stderr!r}")

    # t3: message must contain literal 'ONE-TIME OVERRIDE'
    if "ONE-TIME OVERRIDE" in stderr:
        ok("DENY message contains literal 'ONE-TIME OVERRIDE'")
    else:
        fail_t(f"DENY message missing 'ONE-TIME OVERRIDE' — got: {stderr!r}")

    # t4: message must reference 'rabbit-feature-touch' as the governed path
    if "rabbit-feature-touch" in stderr:
        ok("DENY message references 'rabbit-feature-touch'")
    else:
        fail_t(f"DENY message missing 'rabbit-feature-touch' — got: {stderr!r}")

    # t5: message must mark rabbit-feature-touch as recommended
    if "recommended" in stderr.lower():
        ok("DENY message marks rabbit-feature-touch as recommended")
    else:
        fail_t(f"DENY message missing 'recommended' — got: {stderr!r}")

    # t6: message must state that the override options require
    # in-conversation user confirmation (no speculative writes)
    if "in-conversation user confirmation" in stderr:
        ok("DENY message states overrides require in-conversation user confirmation")
    else:
        fail_t(
            "DENY message missing 'in-conversation user confirmation' "
            f"— got: {stderr!r}"
        )

    # t7: BUG-1 regression — old terse rationalization wording must be gone
    if "Dispatcher must touch .rabbit-scope-active before calling Agent" in stderr:
        fail_t(
            "DENY message still contains the old terse "
            "'Dispatcher must touch .rabbit-scope-active before calling Agent' "
            "wording (BUG-1 regression)"
        )
    else:
        ok("DENY message does NOT contain old terse 'Dispatcher must touch' wording")

    # t8: existing tests scan for 'DENY' — keep that prefix intact
    if "DENY" in stderr:
        ok("DENY message keeps the literal 'DENY' prefix (compat with existing tests)")
    else:
        fail_t(f"DENY message missing literal 'DENY' prefix — got: {stderr!r}")
finally:
    restore()

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
