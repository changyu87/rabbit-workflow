#!/usr/bin/env python3
"""test-start-stop-skill.py — SKILL.md documents start / stop / status
subcommands with their preconditions and marker writes.

Per spec Inv 10:
- `start` verifies three preconditions, writes .rabbit-auto-evolve-running,
  runs one tick, calls ScheduleWakeup.
- `stop` writes .rabbit-auto-evolve-stop-requested; next tick observes it
  and does NOT call ScheduleWakeup.
- `status` is read-only.
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

    # Three preconditions for start.
    required = [
        ".rabbit-auto-evolve-active",
        "human-approval",
        "bypass-permissions",
        # start writes the running marker
        ".rabbit-auto-evolve-running",
        # stop writes the stop marker
        ".rabbit-auto-evolve-stop-requested",
    ]
    for token in required:
        if token not in text:
            print(f"FAIL: SKILL.md missing token: {token}", file=sys.stderr)
            sys.exit(1)

    # status section is read-only.
    if "read-only" not in text:
        print("FAIL: SKILL.md missing 'read-only' descriptor for status",
              file=sys.stderr)
        sys.exit(1)

    print("PASS: test-start-stop-skill.py")


if __name__ == "__main__":
    main()
