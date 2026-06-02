#!/usr/bin/env python3
"""test-tick-skill.py — SKILL.md documents the 12-phase tick algorithm
naming every script and the disk-state path.

Per spec Inv 10: the SKILL.md `tick` subcommand documentation must
enumerate all 12 phases (0..11) and name every Phase C script plus the
disk-state path `.rabbit/auto-evolve-state.json` and mention
`ScheduleWakeup`.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
SKILL_PATH = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-auto-evolve/skills/rabbit-auto-evolve/SKILL.md",
)


def main():
    if not os.path.isfile(SKILL_PATH):
        print(f"FAIL: SKILL.md does not exist at {SKILL_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(SKILL_PATH) as f:
        text = f.read()

    # The 12 phase names from design doc §4.
    phase_names = [
        "stop-check",
        "restart-check",
        "fetch",
        "triage",
        "plan",
        "dispatch",
        "merge",
        "release",
        "cleanup",
        "catch-up",
        "persist",
        "schedule",
    ]
    for name in phase_names:
        if name not in text:
            print(f"FAIL: SKILL.md missing phase name: {name}", file=sys.stderr)
            sys.exit(1)

    # The 10 Phase C scripts that must be named.
    scripts = [
        "set-evolve-mode.py",
        "fetch-queue.py",
        "triage-issue.py",
        "plan-batch.py",
        "safety-check.py",
        "merge-prs.py",
        "release-bump.py",
        "cleanup-branches.py",
        "classify-merge-restart.py",
        "update-state.py",
    ]
    for script in scripts:
        if script not in text:
            print(f"FAIL: SKILL.md missing script name: {script}", file=sys.stderr)
            sys.exit(1)

    # Inv 16 — every script reference must use the full feature-relative
    # prefix `.claude/features/rabbit-auto-evolve/scripts/`. Bare
    # `scripts/<name>.py` is forbidden because Claude resolves SKILL paths
    # relative to the deployed SKILL.md location
    # (`.claude/skills/rabbit-auto-evolve/`), which has no `scripts/` dir.
    import re as _re
    feature_prefix = ".claude/features/rabbit-auto-evolve/scripts/"
    for script in scripts:
        full_ref = feature_prefix + script
        if full_ref not in text:
            print(
                f"FAIL: Inv 16: SKILL.md missing feature-relative reference "
                f"to script: {full_ref}",
                file=sys.stderr,
            )
            sys.exit(1)
        bare_re = _re.compile(
            r"(?<!\.claude/features/rabbit-auto-evolve/)scripts/"
            + _re.escape(script)
        )
        if bare_re.search(text):
            print(
                f"FAIL: Inv 16: bare `scripts/{script}` found in SKILL.md; "
                f"every reference must use the full feature-relative prefix",
                file=sys.stderr,
            )
            sys.exit(1)

    if ".rabbit/auto-evolve-state.json" not in text:
        print("FAIL: SKILL.md missing disk-state path .rabbit/auto-evolve-state.json",
              file=sys.stderr)
        sys.exit(1)

    if "ScheduleWakeup" not in text:
        print("FAIL: SKILL.md missing ScheduleWakeup", file=sys.stderr)
        sys.exit(1)

    print("PASS: test-tick-skill.py")


if __name__ == "__main__":
    main()
