#!/usr/bin/env python3
"""Terminology test: no legacy B/B vocabulary on rabbit-issue live surfaces.

Issue #660 (part of #420 — retire B/B terminology). rabbit-issue's current
vocabulary is "issue" / "bug or enhancement" / "rabbit-managed issue"
(GitHub's bug/enhancement taxonomy). The retired custom "bug-and-backlog"
system that rabbit-issue REPLACED may still be NARRATED as history, but:

  1. The "(B/B)" abbreviation MUST NOT appear on any live surface — it was
     a label for the old custom store and reads as current vocabulary.
  2. "bug-and-backlog" / "bug/backlog" / "bug and backlog" MUST NOT be used
     as LIVE vocabulary (i.e. describing what rabbit-issue IS). The literal
     `origin/bug-backlog-files` branch name is a real historical artifact
     and is exempt (it names the retired branch, not current vocabulary).

Surfaces checked: docs/spec.md, docs/contract.md,
skills/rabbit-issue/SKILL.md, feature.json.

These are static checks; they do not exercise runtime behaviour.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]

SURFACES = (
    FEATURE_DIR / "docs" / "spec.md",
    FEATURE_DIR / "docs" / "contract.md",
    FEATURE_DIR / "skills" / "rabbit-issue" / "SKILL.md",
    FEATURE_DIR / "feature.json",
)

# The "(B/B)" abbreviation and bare "B/B" token are unconditionally banned.
BB_ABBREV = re.compile(r"\bB/B\b")

# "bug-and-backlog" family used as live vocabulary. The literal branch name
# `bug-backlog-files` is a real historical artifact and is exempt.
BB_PHRASE = re.compile(r"bug[- ]and[- ]backlog|bug/backlog", re.IGNORECASE)


def check(path: Path) -> list[str]:
    fails = []
    if not path.is_file():
        fails.append(f"{path} does not exist")
        return fails
    text = path.read_text()
    for lineno, line in enumerate(text.splitlines(), 1):
        if BB_ABBREV.search(line):
            fails.append(
                f"{path}:{lineno} contains banned 'B/B' abbreviation: "
                f"{line.strip()!r}"
            )
        if BB_PHRASE.search(line):
            fails.append(
                f"{path}:{lineno} contains legacy 'bug-and-backlog' "
                f"vocabulary: {line.strip()!r}"
            )
    return fails


def main() -> int:
    all_fails: list[str] = []
    for p in SURFACES:
        all_fails.extend(check(p))
    if all_fails:
        for msg in all_fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-bb-terminology")
    return 0


if __name__ == "__main__":
    sys.exit(main())
