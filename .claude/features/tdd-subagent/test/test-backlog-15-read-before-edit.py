#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BACKLOG-15 LOW F3.
#
# The assembled TDD subagent prompt (or the agents/tdd-subagent.md agent
# spec) MUST include a Read-before-Edit warning. The Claude Code Edit tool
# rejects Edit calls against files that have not been Read in the current
# session; without this warning the subagent learns the rule only by hitting
# the error mid-cycle.
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent")
DISPATCH = os.path.join(FEATURE_DIR, "scripts", "dispatch-tdd-subagent.py")
AGENT_MD = os.path.join(FEATURE_DIR, "agents", "tdd-subagent.md")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")


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


def main():
    # The warning may live in either the assembled prompt's STEP 6 IMPLEMENT
    # section or in agents/tdd-subagent.md (both are read by the subagent
    # at dispatch time). Accept either as the source of truth.
    with open(AGENT_MD) as f:
        agent_content = f.read()
    r = run_dispatch()
    if r.returncode != 0:
        print(f"FAIL: dispatch rc={r.returncode}, stderr={r.stderr}")
        return 1
    prompt = r.stdout

    # The phrasing is intentionally loose — we want the constraint, not a
    # specific wording. The key tokens are "Read" and "Edit" appearing
    # together in a directive about edit-target files.
    candidates = [
        "Read it",
        "Read the file",
        "Read before",
        "read-before-edit",
        "Read-before-Edit",
    ]

    # Check STEP 6 IMPLEMENT section of the assembled prompt first.
    found_in_prompt = False
    if "STEP 6 — IMPLEMENT" in prompt and "STEP 7" in prompt:
        s = prompt.index("STEP 6 — IMPLEMENT")
        e = prompt.index("STEP 7", s)
        step6 = prompt[s:e]
        if any(c in step6 for c in candidates) and "Edit" in step6:
            found_in_prompt = True

    # Or check agents/tdd-subagent.md.
    found_in_agent = (
        any(c in agent_content for c in candidates) and "Edit" in agent_content
    )

    if not (found_in_prompt or found_in_agent):
        print("FAIL: Read-before-Edit warning not found in STEP 6 of the "
              "assembled prompt nor in agents/tdd-subagent.md")
        return 1
    where = "prompt STEP 6" if found_in_prompt else "agents/tdd-subagent.md"
    print(f"PASS: Read-before-Edit warning present ({where})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
