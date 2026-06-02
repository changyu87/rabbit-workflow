#!/usr/bin/env python3
"""test-skill-no-askuserquestion-rule.py — SKILL.md Red Flags section
contains the literal in-loop AskUserQuestion ban rule per spec Inv 13.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
SKILL_PATH = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-auto-evolve/skills/rabbit-auto-evolve/SKILL.md",
)

LITERAL = "MUST NOT emit `AskUserQuestion` calls"


def main():
    if not os.path.isfile(SKILL_PATH):
        print(f"FAIL: SKILL.md does not exist at {SKILL_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(SKILL_PATH) as f:
        text = f.read()

    if LITERAL not in text:
        print(f"FAIL: SKILL.md missing literal rule string: {LITERAL!r}",
              file=sys.stderr)
        sys.exit(1)

    print("PASS: test-skill-no-askuserquestion-rule.py")


if __name__ == "__main__":
    main()
