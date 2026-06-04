#!/usr/bin/env python3
"""Issue #664 (part of #420): legacy B/B vocabulary retired on live surfaces.

Asserts that the legacy bug-and-backlog ("B/B") system vocabulary no longer
appears on rabbit-feature's LIVE surfaces (docs/spec.md, docs/contract.md,
feature.json, and each skills/*/SKILL.md). The current vocabulary is the
rabbit-issue model ("issue" / "bug or enhancement" / "rabbit-managed issue").

Load-bearing literals are exempt: a token is only a violation when it is
B/B-system *vocabulary*. A real branch name, regex token, enum value, or a
code-backed directory path that happens to contain the substring is exempt.
At the time of writing there are no such load-bearing literals on the live
surfaces (the only prior hits — a stale `bug|backlog` CLI enum in
contract.md that the real dispatch script no longer accepts, and a
descriptive `(bug filing, backlog filing)` aside in the touch SKILL.md —
are B/B vocabulary, not load-bearing).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the B/B / bug-and-backlog terminology is fully
retired repo-wide and a cross-feature vocabulary guard subsumes this check.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]

# Live surfaces only (test files, scripts, and CHANGELOG are excluded:
# historical narration in those is allowed).
LIVE_SURFACES = [
    FEATURE_DIR / "docs/spec.md",
    FEATURE_DIR / "docs/contract.md",
    FEATURE_DIR / "feature.json",
]
LIVE_SURFACES += sorted(FEATURE_DIR.glob("skills/*/SKILL.md"))

# Legacy B/B-system vocabulary patterns. Case-insensitive where noted.
BB_PATTERNS = [
    re.compile(r"\bB/B\b"),
    re.compile(r"bug-and-backlog", re.IGNORECASE),
    re.compile(r"bug\s+and\s+backlog", re.IGNORECASE),
    re.compile(r"bug\|backlog", re.IGNORECASE),
    re.compile(r"\bbacklog\b", re.IGNORECASE),
]

# Load-bearing literals to exempt: exact substrings that, although they
# contain a banned token, are a real branch name / regex token / enum value /
# code-backed path the implementation depends on. Empty for now — if a future
# edit must reintroduce a real `backlog` literal, add it here with a comment
# explaining why it is load-bearing.
EXEMPT_SUBSTRINGS: list[str] = []


def _violations(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    hits: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if any(ex in line for ex in EXEMPT_SUBSTRINGS):
            continue
        for pat in BB_PATTERNS:
            if pat.search(line):
                rel = path.relative_to(FEATURE_DIR)
                hits.append(f"{rel}:{i}: {line.strip()}")
                break
    return hits


def test_no_bb_vocabulary_on_live_surfaces() -> None:
    all_hits: list[str] = []
    for surface in LIVE_SURFACES:
        all_hits.extend(_violations(surface))
    assert not all_hits, (
        "legacy B/B vocabulary found on live surfaces (issue #664); "
        "reword to current rabbit-issue vocabulary or add a documented "
        "exemption if the token is load-bearing:\n" + "\n".join(all_hits)
    )


def main() -> int:
    test_no_bb_vocabulary_on_live_surfaces()
    print("OK: no legacy B/B vocabulary on rabbit-feature live surfaces")
    return 0


if __name__ == "__main__":
    sys.exit(main())
