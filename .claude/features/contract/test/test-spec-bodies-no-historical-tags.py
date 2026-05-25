#!/usr/bin/env python3
"""test-spec-bodies-no-historical-tags.py — CONTRACT-BACKLOG-38.

Greps every feature's docs/spec/spec.md for historical-burden patterns
that violate housekeeping protocol criterion #1 (current-design only)
and criterion #2 (no documentation burden):

    Plan [A-F]      — cleanup wave / plan identifiers
    BUG-N           — bug item references
    BACKLOG-N       — backlog item references
    Wave N          — wave identifiers

Such tags belong in commit messages and CHANGELOG.md tombstones, NOT
in spec bodies. Spec bodies describe the CURRENT design; the project
ticket that produced any given line is irrelevant once the line ships.

A hardcoded ALLOWLIST permits legitimate occurrences (algorithm-output
examples whose textual content happens to match the pattern).

Non-interactive. Exits non-zero on any unallowlisted match.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")

PATTERN = re.compile(r"Plan [A-F]|BUG-[0-9]|BACKLOG-[0-9]|Wave [0-9]")

# (relative-from-features-root, line_number, substring-on-line) tuples.
# Each entry records a legitimate occurrence and WHY it is permitted.
# Update only after manual review confirms the line is not a project
# tag but a genuine value (e.g. algorithm-output sample).
ALLOWLIST = {
    # rabbit-file algorithm output examples — these are sample values
    # the ID-generation algorithm produces, demonstrating its output
    # shape. The strings do not refer to real bug/backlog items.
    ("rabbit-file/docs/spec/spec.md", 33, "RABBIT-CAGE-BUG-17"),
    ("rabbit-file/docs/spec/spec.md", 34, "MY-FEATURE-X-BACKLOG-3"),
    ("rabbit-file/docs/spec/spec.md", 35, "SINGLE-BUG-1"),
}


def feature_spec_files():
    paths = []
    for entry in sorted(os.listdir(FEATURES_ROOT)):
        spec = os.path.join(FEATURES_ROOT, entry, "docs", "spec", "spec.md")
        if os.path.isfile(spec):
            paths.append((entry, spec))
    return paths


def is_allowlisted(rel_path, line_no, line_text):
    for a_path, a_line, a_substr in ALLOWLIST:
        if a_path == rel_path and a_line == line_no and a_substr in line_text:
            return True
    return False


violations = []
for feature, spec_path in feature_spec_files():
    rel_path = os.path.relpath(spec_path, FEATURES_ROOT)
    with open(spec_path) as f:
        for line_no, line in enumerate(f, start=1):
            if PATTERN.search(line):
                if is_allowlisted(rel_path, line_no, line.rstrip("\n")):
                    continue
                violations.append((rel_path, line_no, line.rstrip("\n")))

if violations:
    print("FAIL: historical-burden tags found in spec bodies", file=sys.stderr)
    for rel, ln, txt in violations:
        print(f"  {rel}:{ln}: {txt}", file=sys.stderr)
    print(
        f"\n{len(violations)} violation(s). "
        "Scrub tags from spec bodies (preserve in commit messages and "
        "CHANGELOG tombstones), or add to ALLOWLIST after review.",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"PASS: no historical-burden tags in {len(feature_spec_files())} spec.md files")
sys.exit(0)
