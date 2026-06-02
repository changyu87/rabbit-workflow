#!/usr/bin/env python3
"""test-discovered-issues.py — SKILL.md documents the discovered_issues
and aborted_reason HANDOFF handling per spec Inv 10 / design §6.

When a TDD subagent's HANDOFF carries `discovered_issues`, the loop files
each via rabbit-issue; when `aborted_reason` is set, the loop labels
`blocked-by:#N` on the original issue and leaves it open.
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

    required = [
        "discovered_issues",
        "aborted_reason",
        "blocked-by:",
        "rabbit-issue",
    ]
    for token in required:
        if token not in text:
            print(f"FAIL: SKILL.md missing token: {token}", file=sys.stderr)
            sys.exit(1)

    print("PASS: test-discovered-issues.py")


if __name__ == "__main__":
    main()
