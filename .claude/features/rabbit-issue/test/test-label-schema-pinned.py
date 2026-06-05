#!/usr/bin/env python3
"""Pin the documented label schema across rabbit-issue doc surfaces.

The label schema is the load-bearing contract of rabbit-issue: the type
labels, the `feature:` / `priority:` required labels, the `filed-by:`
provenance enum, the `housekeeping` category label, and the `in-progress`
loop-managed category label. A measured-reduction housekeeping pass trims
redundant prose; this guard ensures it can never silently drop a documented
label token from the doc surfaces.

Invariants:

  1. docs/spec.md MUST document every label token in its label-schema table:
     `bug`, `enhancement`, `feature:<name>`, `priority:`, `filed-by:`,
     `housekeeping`, and `in-progress`.
  2. docs/contract.md MUST list the same seven label tokens in its
     `issue_labels` provides block.
  3. The `filed-by:` provenance enum MUST name BOTH non-human values
     (`rabbit`, `autonomous-evolve`) on the spec surface, since human is the
     untagged default and the enum is closed.

These are static checks; runtime label behaviour is exercised by
test-file-item.py and test-ensure-labels.py.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
from __future__ import annotations

import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
CONTRACT_MD = FEATURE_DIR / "docs" / "contract.md"

# Load-bearing label tokens that MUST survive any reduction pass.
SPEC_TOKENS = (
    "`bug`",
    "`enhancement`",
    "feature:<name>",
    "`priority:",
    "filed-by:",
    "`housekeeping`",
    "`in-progress`",
)
CONTRACT_TOKENS = (
    '"bug"',
    '"enhancement"',
    "feature:<name>",
    "priority:<low|medium|high|critical>",
    "filed-by:<rabbit|autonomous-evolve>",
    '"housekeeping"',
    '"in-progress"',
)
# The provenance enum is closed; both non-human values must be named.
PROVENANCE_VALUES = ("rabbit", "autonomous-evolve")


def check_tokens(path: Path, tokens) -> list[str]:
    fails = []
    if not path.is_file():
        fails.append(f"{path} does not exist")
        return fails
    text = path.read_text()
    for tok in tokens:
        if tok not in text:
            fails.append(f"{path} missing required label token {tok!r}")
    return fails


def check_provenance_enum() -> list[str]:
    fails = []
    text = SPEC_MD.read_text()
    for val in PROVENANCE_VALUES:
        if val not in text:
            fails.append(
                f"{SPEC_MD} missing provenance enum value {val!r}"
            )
    return fails


def main() -> int:
    all_fails: list[str] = []
    all_fails.extend(check_tokens(SPEC_MD, SPEC_TOKENS))
    all_fails.extend(check_tokens(CONTRACT_MD, CONTRACT_TOKENS))
    all_fails.extend(check_provenance_enum())
    if all_fails:
        for msg in all_fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-label-schema-pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
