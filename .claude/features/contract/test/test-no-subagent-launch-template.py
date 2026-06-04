#!/usr/bin/env python3
"""test-no-subagent-launch-template.py — assert the dead
templates/subagent-launch-template.txt is absent on disk (Inv 48).

The template was a never-consumed prototype superseded by the per-callable
templates under templates/prompts/ (Inv 47) and the build-prompt.py
assembler (Inv 46). Its continued presence would be dead surface; this
test enforces deletion.

Exit codes:
  0 — file absent (pass)
  1 — file present (fail)
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEAD = REPO_ROOT / ".claude/features/contract/templates/subagent-launch-template.txt"


def main():
    if DEAD.exists():
        print(f"FAIL: dead template still present: {DEAD}", file=sys.stderr)
        return 1
    print("OK: dead template absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
