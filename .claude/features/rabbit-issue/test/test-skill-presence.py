#!/usr/bin/env python3
"""Presence and frontmatter tests for rabbit-issue SKILL.md.

Skill-side invariants enforced (per spec-rules.md §3 and the rabbit-issue
spec's "Surface" section):

  1. skills/rabbit-issue/SKILL.md MUST exist with a YAML frontmatter block
     carrying name / version / owner / deprecation_criterion.
  2. The frontmatter `name` field MUST be exactly `rabbit-issue`.
  3. The SKILL.md body MUST mention that rabbit-issue REPLACES the retired
     rabbit-file feature (so triggering routes here, not to rabbit-file).
  4. The SKILL.md body MUST document the `rabbit-managed` safety guard
     (Work Protocol invariant from the spec).

These are static checks; runtime behaviour is exercised by the
file-item / item-status / list-items pytest suites.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit-issue is retired
"""
from __future__ import annotations

import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SKILL_MD = FEATURE_DIR / "skills" / "rabbit-issue" / "SKILL.md"

REQUIRED_FM_KEYS = ("name:", "version:", "owner:", "deprecation_criterion:")


def check(path: Path) -> list[str]:
    """Return a list of failure messages for `path` (empty list = pass)."""
    fails = []
    if not path.is_file():
        fails.append(f"{path} does not exist")
        return fails
    text = path.read_text()
    if not text.startswith("---\n"):
        fails.append(f"{path} missing leading YAML frontmatter block")
        return fails
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        fails.append(f"{path} has unterminated YAML frontmatter")
        return fails
    fm, body = parts[1], parts[2]
    for key in REQUIRED_FM_KEYS:
        if key not in fm:
            fails.append(f"{path} frontmatter missing key '{key}'")
    # name MUST be exactly rabbit-issue (anchored to its own line)
    if "name: rabbit-issue" not in fm:
        fails.append(f"{path} frontmatter `name` is not 'rabbit-issue'")
    # Body MUST mention rabbit-file replacement (routing invariant)
    if "rabbit-file" not in body:
        fails.append(
            f"{path} body MUST mention rabbit-file (replacement notice)"
        )
    # Body MUST document the rabbit-managed safety guard
    if "rabbit-managed" not in body:
        fails.append(
            f"{path} body MUST document the `rabbit-managed` safety guard"
        )
    return fails


def main() -> int:
    all_fails = check(SKILL_MD)
    if all_fails:
        for msg in all_fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-skill-presence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
