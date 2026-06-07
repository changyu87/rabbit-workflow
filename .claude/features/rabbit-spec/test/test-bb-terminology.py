#!/usr/bin/env python3
"""Inv 7: no legacy B/B vocabulary on rabbit-spec live surfaces.

Issue #666 (part of #420 — retire B/B terminology). rabbit-spec's current
vocabulary is "issue" / "bug or enhancement" / "rabbit-managed issue"
(GitHub's bug/enhancement taxonomy). The retired custom "bug-and-backlog"
system may still be NARRATED as history, but the following are banned as
LIVE vocabulary on the surfaces below:

  1. The "B/B" abbreviation MUST NOT appear — it labelled the old custom
     store and reads as current vocabulary.
  2. The "bug-and-backlog" / "bug/backlog" / "bug and backlog" phrase family
     MUST NOT be used as LIVE vocabulary (describing what rabbit-spec inputs
     or classifies).
  3. Standalone "backlog" used as a request-class noun ("backlog task",
     "backlog item", "backlog items") MUST NOT survive — the current class
     noun is "enhancement". The literal branch name `bug-backlog-files`
     remains a real historical artifact and is exempt.

Surfaces checked: docs/spec.md, docs/contract.md,
agents/rabbit-spec-creator.md, skills/rabbit-spec-update/SKILL.md,
feature.json.

These are static checks; they do not exercise runtime behaviour.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-spec is retired
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]

SURFACES = (
    FEATURE_DIR / "docs" / "spec.md",
    FEATURE_DIR / "docs" / "contract.md",
    FEATURE_DIR / "agents" / "rabbit-spec-creator.md",
    FEATURE_DIR / "skills" / "rabbit-spec-update" / "SKILL.md",
    FEATURE_DIR / "feature.json",
)

# The "B/B" abbreviation is unconditionally banned.
BB_ABBREV = re.compile(r"\bB/B\b")

# "bug-and-backlog" family used as live vocabulary.
BB_PHRASE = re.compile(r"bug[- ]and[- ]backlog|bug/backlog", re.IGNORECASE)

# Standalone "backlog" as a request-class noun. The literal branch name
# `bug-backlog-files` is a real historical artifact and is exempt.
BACKLOG_WORD = re.compile(r"\bbacklog\b", re.IGNORECASE)
BACKLOG_EXEMPT = re.compile(r"bug-backlog-files")


def check(path: Path) -> list[str]:
    fails = []
    if not path.is_file():
        fails.append(f"{path} does not exist")
        return fails
    text = path.read_text()
    for lineno, line in enumerate(text.splitlines(), 1):
        if BB_ABBREV.search(line):
            fails.append(
                f"{path.name}:{lineno} contains banned 'B/B' abbreviation: "
                f"{line.strip()!r}"
            )
        if BB_PHRASE.search(line):
            fails.append(
                f"{path.name}:{lineno} contains legacy 'bug-and-backlog' "
                f"vocabulary: {line.strip()!r}"
            )
        if BACKLOG_WORD.search(line) and not BACKLOG_EXEMPT.search(line):
            fails.append(
                f"{path.name}:{lineno} contains standalone 'backlog' "
                f"request-class noun: {line.strip()!r}"
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
