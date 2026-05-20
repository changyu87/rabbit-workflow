#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BUG-57 (constitution conflict: inline ANSI/brand
# bypass-note emission must route through the dispatch_bypass_note() wrapper
# from contract.scripts.rabbit_print). Spec v2.1.0 Inv 17 rewritten in this
# cycle: the wrapper is the only authorized emission path; inline ANSI escape
# codes and brand strings in dispatch-tdd-subagent.py are forbidden.
#
# Checks:
#   t1: dispatch output preamble (slice before STEP 1) contains the EXACT
#       string returned by dispatch_bypass_note() when the bypass marker
#       exists. Byte-identity is the contract — if the wrapper is bypassed
#       (inline string) the strings will diverge.
#   t2: dispatch-tdd-subagent.py source contains no inline ANSI escape
#       sequences and no inline canonical brand string. The wrapper is the
#       sole authorized emission site.
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent")
DISPATCH = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
MARKER = os.path.join(REPO_ROOT, ".rabbit-human-approval-bypass")

# Import the wrapper under test (the contract-feature surface).
sys.path.insert(
    0, os.path.join(REPO_ROOT, ".claude", "features", "contract", "scripts")
)
from rabbit_print import dispatch_bypass_note  # noqa: E402

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def run_dispatch():
    env = os.environ.copy()
    env["RABBIT_ROOT"] = REPO_ROOT
    return subprocess.run(
        [sys.executable, DISPATCH, "--scope", "tdd-subagent", "--spec", SPEC_MD],
        capture_output=True, text=True, env=env,
    )


# t1: preamble contains exact dispatch_bypass_note() output when marker exists.
def t1():
    marker_existed = os.path.isfile(MARKER)
    if not marker_existed:
        with open(MARKER, "w") as f:
            f.write("")
    try:
        r = run_dispatch()
        if r.returncode != 0:
            ko(f"t1: dispatch rc={r.returncode}, stderr={r.stderr}")
            return
        expected = dispatch_bypass_note()
        if "STEP 1" not in r.stdout:
            ko("t1: dispatch stdout missing STEP 1 marker")
            return
        preamble = r.stdout.split("STEP 1", 1)[0]
        if expected not in preamble:
            ko("t1: preamble does not contain exact dispatch_bypass_note() output "
               "(BUG-57: wrapper bypassed by inline emission)")
            return
        ok("t1: preamble contains exact dispatch_bypass_note() wrapper output")
    finally:
        if not marker_existed and os.path.isfile(MARKER):
            os.unlink(MARKER)


# t2: dispatch script source has no inline ANSI / brand strings at the
# bypass-note emission site (the wrapper is the only authorized producer).
def t2():
    with open(DISPATCH) as f:
        src = f.read()
    # Inline ANSI escape literal must be absent. The wrapper renders \x1b[33m
    # internally; the dispatch script must not author it directly.
    if "\\x1b[" in src or "\x1b[" in src:
        ko("t2: dispatch script contains inline ANSI escape sequence "
           "(BUG-57: inline emission forbidden)")
        return
    # Canonical brand string `[🐇 rabbit 🐇]` must not appear inline as a
    # literal in this script — only the wrapper produces it.
    if "[\U0001f407 rabbit \U0001f407]" in src:
        ko("t2: dispatch script contains inline canonical brand string "
           "(BUG-57: only dispatch_bypass_note() may emit it)")
        return
    ok("t2: dispatch script has no inline ANSI or brand strings")


t1()
t2()

print()
if FAIL == 0:
    print(f"bug-57: {PASS} passed.")
    sys.exit(0)
print(f"bug-57: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
