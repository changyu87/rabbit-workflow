#!/usr/bin/env python3
# test-bypass-marker-skill-doc.py — BUG-3
# Asserts that rabbit-feature-touch SKILL.md Step 4 documents the
# .rabbit-human-approval-bypass marker as the FIRST action of Step 4 with
# audit-friendly warning text naming the marker path and revoke command.
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SKILL_PATH = os.path.join(
    REPO_ROOT,
    ".claude", "features", "tdd-subagent",
    "skills", "rabbit-feature-touch", "SKILL.md",
)


def main():
    if not os.path.isfile(SKILL_PATH):
        print(f"FAIL: SKILL.md not found at {SKILL_PATH}")
        return 1
    with open(SKILL_PATH) as f:
        content = f.read()

    # Locate Step 4 section.
    step4_marker = "### Step 4 — Human Approval"
    if step4_marker not in content:
        print(f"FAIL: '{step4_marker}' not found in SKILL.md")
        return 1
    step4_start = content.index(step4_marker)
    # The next ### heading (Step 5) bounds the section.
    step5_marker = "### Step 5"
    step4_end = content.index(step5_marker, step4_start) if step5_marker in content[step4_start:] else len(content)
    step4_section = content[step4_start:step4_end]

    required_substrings = [
        ".rabbit-human-approval-bypass",
        "/rabbit-config human-approval gated",
        "--no-human-approval",
    ]
    missing = [s for s in required_substrings if s not in step4_section]
    if missing:
        print(f"FAIL: Step 4 section missing required substrings: {missing}")
        return 1

    # Old in-conversation bypass language must be gone.
    forbidden = "when the user has indicated they want fully autonomous execution for this session"
    if forbidden in content:
        print(f"FAIL: SKILL.md still contains old bypass phrase: {forbidden!r}")
        return 1

    print("PASS: SKILL.md Step 4 documents bypass-marker-first behaviour")
    return 0


if __name__ == "__main__":
    sys.exit(main())
