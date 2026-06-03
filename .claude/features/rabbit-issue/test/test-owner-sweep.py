#!/usr/bin/env python3
"""Owner-sweep invariants for rabbit-issue (issue #416).

Enforces that no owner field, frontmatter, or module docstring within the
rabbit-issue feature names an individual. The single accepted owner value is
the team identity "rabbit-workflow team".

Invariants:
  1. feature.json top-level owner == "rabbit-workflow team".
  2. No owner-bearing line anywhere under the feature tree names an
     individual (no owner marker followed by the individual login remains).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature ownership is tracked natively by the
    workflow registry rather than per-file owner markers.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"

EXPECTED_OWNER = "rabbit-workflow team"

# The individual login that must no longer appear as an owner value.
# Kept as a separate constant so this test's own source carries no literal
# "owner: <login>" pattern that would match itself.
INDIVIDUAL_LOGIN = "cyxu"

# Match an owner marker (owner:/Owner:/"owner":) directly assigning the
# individual login, in YAML frontmatter, JSON, docstrings, or shell comments.
INDIVIDUAL_OWNER_RE = re.compile(
    r'owner"?\s*:\s*"?' + re.escape(INDIVIDUAL_LOGIN) + r"\b",
    re.IGNORECASE,
)

SCAN_SUFFIXES = {".py", ".sh", ".md", ".json"}


def main() -> int:
    fails: list[str] = []

    data = json.loads(FEATURE_JSON.read_text())
    if data.get("owner") != EXPECTED_OWNER:
        fails.append(
            f"feature.json owner must be {EXPECTED_OWNER!r}, "
            f"got {data.get('owner')!r}"
        )

    for path in sorted(FEATURE_DIR.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        text = path.read_text(errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if INDIVIDUAL_OWNER_RE.search(line):
                rel = path.relative_to(FEATURE_DIR)
                fails.append(
                    f"{rel}:{lineno} names individual owner: {line.strip()!r}"
                )

    if fails:
        for msg in fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-owner-sweep")
    return 0


if __name__ == "__main__":
    sys.exit(main())
