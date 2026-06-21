#!/usr/bin/env python3
"""test-spec-housekeeping-1185-no-historical-tags.py — issue #1185.

Own-feature mirror of the contract repo-gate
`contract/test/test-spec-bodies-no-historical-tags.py`, scoped to
rabbit-auto-evolve's OWN doc body surfaces (docs/spec.md, docs/contract.md).

rabbit-auto-evolve opted into the strict tier (`housekeeping_clean: true`),
so bare `#NNNN` issue/PR provenance tags in its spec/contract BODY prose are
forbidden: such tags belong in CHANGELOG.md tombstones and commit messages,
not in current-design doc surfaces. `Inv NN` invariant references are NOT
historical tags and are unaffected by this check (the pattern only matches
`#` immediately followed by digits). This is a same-feature regression guard
so the scrub stays scrubbed without waiting for the cross-feature contract
gate.

The single permitted occurrence is the live `feature.json.status ==
"retired"` status-enum literal on the Inv 19 triage decision-table row,
which the contract gate's production ALLOWLIST also permits — it is a
load-bearing status-enum value the triage interpreter checks verbatim, not a
historical-burden tombstone. The contract gate's `superseded/retired/
obsoleted` tombstone-word tier is owned by that gate; this same-feature guard
scopes to the bare `#NNNN` class that #1185 scrubbed.

Non-interactive. Exits non-zero on any unallowlisted match.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))

# Same bare-issue-tag pattern the contract strict tier rejects: `#` + digits.
TAG_PATTERN = re.compile(r"#[0-9]+")

# Live status-enum literal — permitted (mirrors the contract gate allowlist).
ALLOWED_SUBSTRINGS = (
    'feature.json.status == "retired"',
)

SURFACES = [
    os.path.join(FEATURE_DIR, "docs", "spec.md"),
    os.path.join(FEATURE_DIR, "docs", "contract.md"),
]

violations = []
for surface in SURFACES:
    if not os.path.isfile(surface):
        print(f"FAIL: missing surface: {surface}", file=sys.stderr)
        sys.exit(1)
    with open(surface) as f:
        for line_no, line in enumerate(f, start=1):
            if not TAG_PATTERN.search(line):
                continue
            if any(sub in line for sub in ALLOWED_SUBSTRINGS):
                continue
            violations.append((os.path.basename(surface), line_no,
                               line.rstrip("\n")))

if violations:
    print("FAIL: bare #NNNN historical tags found in rabbit-auto-evolve "
          "doc body surfaces", file=sys.stderr)
    for name, ln, txt in violations:
        print(f"  docs/{name}:{ln}: {txt}", file=sys.stderr)
    print(f"\n{len(violations)} violation(s). Scrub bare #NNNN tags from "
          "spec/contract body prose (preserve in CHANGELOG / commit "
          "messages); keep Inv NN references.", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-1185-no-historical-tags: no bare #NNNN tags "
      "in rabbit-auto-evolve doc body surfaces.")
sys.exit(0)
