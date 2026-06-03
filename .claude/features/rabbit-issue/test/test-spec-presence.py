#!/usr/bin/env python3
"""Presence and frontmatter tests for rabbit-issue spec.md and contract.md.

Spec-side invariants enforced (per spec-rules.md §3):

  1. docs/spec/spec.md MUST exist with a YAML frontmatter block carrying
     feature / version / owner / deprecation_criterion.
  2. docs/spec/contract.md MUST exist with the same frontmatter shape.

These are static checks; they do not exercise runtime behaviour.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
from __future__ import annotations

import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"
CONTRACT_MD = FEATURE_DIR / "docs" / "spec" / "contract.md"

REQUIRED_FM_KEYS = ("feature:", "version:", "owner:", "deprecation_criterion:")


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
    fm = parts[1]
    for key in REQUIRED_FM_KEYS:
        if key not in fm:
            fails.append(f"{path} frontmatter missing key '{key}'")
    return fails


def main() -> int:
    all_fails: list[str] = []
    for p in (SPEC_MD, CONTRACT_MD):
        all_fails.extend(check(p))
    if all_fails:
        for msg in all_fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-spec-presence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
