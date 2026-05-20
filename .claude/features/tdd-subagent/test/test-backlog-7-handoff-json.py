#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BACKLOG-7.
#
# BACKLOG-7: assembled prompt includes a JSON HANDOFF schema (HANDOFF_JSON
#            block + handoff_schema_version) alongside YAML HANDOFF.
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent")
DISPATCH = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")

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
        [
            sys.executable,
            DISPATCH,
            "--scope", "tdd-subagent",
            "--spec", SPEC_MD,
        ],
        capture_output=True, text=True, env=env,
    )


# BACKLOG-7: assembled prompt has HANDOFF_JSON block and handoff_schema_version.
# The check inspects the prompt AFTER the SPEC body so spec text alone does
# not satisfy the test (the spec mentions HANDOFF_JSON when documenting the
# behaviour, but the prompt MUST also include an instruction block).
def b7():
    r = run_dispatch()
    if r.returncode != 0:
        ko(f"b7: dispatch failed: {r.stderr}")
        return
    out = r.stdout
    # Slice off everything up to and including the SPEC body so we only
    # inspect prompt instructions the dispatcher itself authored.
    if "STEP 9 — UNLOCK" not in out:
        ko("b7: prompt missing STEP 9 — UNLOCK heading")
        return
    tail = out[out.index("STEP 9 — UNLOCK"):]
    if "HANDOFF_JSON:" not in tail:
        ko("b7: prompt missing 'HANDOFF_JSON:' marker after STEP 9")
        return
    if "handoff_schema_version" not in tail:
        ko("b7: prompt missing 'handoff_schema_version' field after STEP 9")
        return
    if '"1.0.0"' not in tail:
        ko("b7: prompt missing handoff schema version '1.0.0' after STEP 9")
        return
    # Legacy YAML HANDOFF must also remain for backward compatibility.
    if "HANDOFF:" not in tail:
        ko("b7: prompt missing legacy 'HANDOFF:' block after STEP 9")
        return
    ok("b7: prompt includes structured HANDOFF_JSON schema v1.0.0 + legacy YAML")


b7()

print()
if FAIL == 0:
    print(f"backlog-7: {PASS} passed.")
    sys.exit(0)
print(f"backlog-7: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
