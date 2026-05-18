#!/usr/bin/env python3
# test-human-approval-gate-flag.py
# E2E asserts the renamed --human-approval-gate true|false flag on
# dispatch-tdd-subagent.py per Inv 12 / Inv 15 of tdd-subagent spec v1.9.0.
#
# Behaviours covered:
#   - --human-approval-gate true → assembled prompt contains the full
#     HUMAN-APPROVAL section.
#   - --human-approval-gate false → assembled prompt contains
#     "Skipped (--human-approval-gate false)." and no full section body.
#   - no flag → defaults to gate active (full section, same as 'true').
#   - --human-approval-gate enabled → rejected (argparse choices).
#   - --no-human-approval → flag no longer recognized (rejected).
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPT_DIR, "..", "scripts", "dispatch-tdd-subagent.py")
REPO_ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"], cwd=SCRIPT_DIR
).decode().strip()
SPEC = os.path.join(REPO_ROOT, ".claude/features/tdd-subagent/docs/spec/spec.md")

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


def run(args):
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True, text=True, check=False,
    )


# Full HUMAN-APPROVAL section signature — present when gate is active.
FULL_SECTION_SIGNATURE = "superpowers:writing-plans"
SKIP_LINE = "Skipped (--human-approval-gate false)."


# 1. --human-approval-gate true → full HUMAN-APPROVAL section.
r = run(["--scope", "tdd-subagent", "--spec", SPEC, "--human-approval-gate", "true"])
if r.returncode != 0:
    ko(f"--human-approval-gate true should be accepted (got rc={r.returncode}, stderr={r.stderr!r})")
elif FULL_SECTION_SIGNATURE not in r.stdout:
    ko("--human-approval-gate true: prompt missing full HUMAN-APPROVAL section")
elif SKIP_LINE in r.stdout:
    ko("--human-approval-gate true: prompt unexpectedly contains skip line")
else:
    ok("--human-approval-gate true → full HUMAN-APPROVAL section emitted")

# 2. --human-approval-gate false → skip line, no full section.
r = run(["--scope", "tdd-subagent", "--spec", SPEC, "--human-approval-gate", "false"])
if r.returncode != 0:
    ko(f"--human-approval-gate false should be accepted (got rc={r.returncode}, stderr={r.stderr!r})")
elif SKIP_LINE not in r.stdout:
    ko(f"--human-approval-gate false: prompt missing {SKIP_LINE!r}")
elif FULL_SECTION_SIGNATURE in r.stdout:
    ko("--human-approval-gate false: prompt unexpectedly contains full HUMAN-APPROVAL section")
else:
    ok("--human-approval-gate false → skip line emitted, full section omitted")

# 3. no flag → defaults to gate active (full section).
r = run(["--scope", "tdd-subagent", "--spec", SPEC])
if r.returncode != 0:
    ko(f"no flag should default to true (got rc={r.returncode}, stderr={r.stderr!r})")
elif FULL_SECTION_SIGNATURE not in r.stdout:
    ko("no flag (default true): prompt missing full HUMAN-APPROVAL section")
elif SKIP_LINE in r.stdout:
    ko("no flag (default true): prompt unexpectedly contains skip line")
else:
    ok("no flag → defaults to gate active (full section emitted)")

# 4. --human-approval-gate enabled → argparse rejection (non-zero exit).
r = run(["--scope", "tdd-subagent", "--spec", SPEC, "--human-approval-gate", "enabled"])
if r.returncode == 0:
    ko("--human-approval-gate enabled should be rejected (choices=true|false)")
else:
    ok("--human-approval-gate enabled → rejected (argparse choices)")

# 5. --no-human-approval → flag no longer recognized (non-zero exit).
r = run(["--scope", "tdd-subagent", "--spec", SPEC, "--no-human-approval"])
if r.returncode == 0:
    ko("--no-human-approval should no longer be recognized")
else:
    ok("--no-human-approval → no longer recognized (rejected)")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
