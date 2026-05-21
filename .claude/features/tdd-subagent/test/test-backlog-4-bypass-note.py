#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BACKLOG-4.
#
# BACKLOG-4: dispatch-tdd-subagent.py emits a distinct yellow [rabbit] note
#            in the prompt preamble when .rabbit-human-approval-bypass exists.
#
# History: the b4 assertion that the preamble note carries the canonical
# `[🐇 rabbit 🐇]` brand prefix was originally cited as "contract Inv 28/29
# and tdd-subagent Inv 5" (BUG-58). The tdd-subagent Inv 5 citation was
# wrong (Inv 5 describes the E2E test rule, not the brand convention) and
# has been dropped. The brand convention lives in contract Inv 27
# (definition) and Inv 29 (producer rule).
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent")
DISPATCH = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
MARKER = os.path.join(REPO_ROOT, ".rabbit-human-approval-bypass")

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


def run_dispatch(extra_env=None):
    env = os.environ.copy()
    env["RABBIT_ROOT"] = REPO_ROOT
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [
            sys.executable,
            DISPATCH,
            "--scope", "tdd-subagent",
            "--spec", SPEC_MD,
        ],
        capture_output=True, text=True, env=env,
    )


# BACKLOG-4: dispatch shows a yellow bypass note when marker exists.
def b4():
    # Marker absent -> no yellow note.
    marker_existed = os.path.isfile(MARKER)
    if marker_existed:
        os.unlink(MARKER)
    try:
        r = run_dispatch()
        if r.returncode != 0:
            ko(f"b4: dispatch failed without marker: {r.stderr}")
            return
        if "HUMAN APPROVAL BYPASS" in r.stdout and "\x1b[33m" in r.stdout:
            ko("b4: yellow bypass note appeared when marker absent (false positive)")
            return
        ok("b4a: no bypass note in prompt when marker absent")

        # Marker present -> yellow note in preamble.
        with open(MARKER, "w") as f:
            f.write("")
        r = run_dispatch()
        if r.returncode != 0:
            ko(f"b4: dispatch failed with marker: {r.stderr}")
            return
        out = r.stdout
        if "\x1b[33m" not in out:
            ko("b4b: prompt missing yellow ANSI \\x1b[33m for bypass note")
            return
        if ".rabbit-human-approval-bypass" not in out:
            ko("b4b: prompt bypass note does not name the marker path")
            return
        if "/rabbit-config human-approval true" not in out:
            ko("b4b: prompt bypass note does not name the revoke skill")
            return
        # Note must be in preamble, before STEP 1 SPEC-READ.
        pre = out.split("STEP 1")[0]
        if "\x1b[33m" not in pre:
            ko("b4b: yellow bypass note not in preamble (before STEP 1)")
            return
        # Inv 17 (spec v2.1.0): brand prefix in the preamble bypass note
        # MUST be the canonical emoji-framed form `[🐇 rabbit 🐇]` per
        # contract Inv 27 (brand definition) / Inv 29 (producer rule).
        # The bare `[rabbit]` form is forbidden. We check the preamble
        # slice (not full output) because the spec body itself documents
        # both forms when describing the rule, which would otherwise mask
        # drift in the note literal.
        if "[\U0001f407 rabbit \U0001f407]" not in pre:
            ko("b4b: preamble bypass note missing canonical [🐇 rabbit 🐇] brand prefix")
            return
        ok("b4b: yellow bypass note in preamble when marker present")
    finally:
        # Restore marker state.
        if os.path.isfile(MARKER):
            os.unlink(MARKER)
        if marker_existed:
            with open(MARKER, "w") as f:
                f.write("")


b4()

print()
if FAIL == 0:
    print(f"backlog-4: {PASS} passed.")
    sys.exit(0)
print(f"backlog-4: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
