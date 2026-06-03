#!/usr/bin/env python3
"""test-spec-bodies-no-historical-tags.py — CONTRACT-BACKLOG-38 / -40.

Greps every feature's spec.md, contract.md (resolved at specs/<name> —
issue #399 migration complete, fallback dropped #465), and any
skills/*/SKILL.md under each feature for historical-burden patterns that
violate housekeeping protocol criterion #1 (current-design only) and
criterion #2 (no documentation burden):

    Plan [A-F]      — cleanup wave / plan identifiers
    BUG-N           — bug item references
    BACKLOG-N       — backlog item references
    Wave N          — wave identifiers

Such tags belong in commit messages and CHANGELOG.md tombstones, NOT
in feature documentation surfaces. Doc surfaces describe the CURRENT
design; the project ticket that produced any given line is irrelevant
once the line ships.

A hardcoded ALLOWLIST permits legitimate occurrences (algorithm-output
examples whose textual content happens to match the pattern).

Non-interactive. Exits non-zero on any unallowlisted match.
"""

import glob
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
    # tdd-subagent spec.md migration note — names the prompt-contract
    # migration backlog (CONTRACT-BACKLOG-1) so future readers can find
    # the design doc and PR stack. The reference is documentary, not a
    # live project-management tag, and the migration is a permanent
    # architectural fact.
    ("tdd-subagent/specs/spec.md", 60, "CONTRACT-BACKLOG-1"),
}


def _resolve_doc(fdir, name):
    """Resolve specs/<name> (issue #399 migration complete, fallback dropped
    #465). Returns the existing path or None."""
    path = os.path.join(fdir, "specs", name)
    if os.path.isfile(path):
        return path
    return None


def feature_doc_surfaces():
    """Yield (feature_name, abs_path) for every monitored doc surface:
    spec.md, contract.md (each resolved at specs/<name>), and
    skills/*/SKILL.md.
    """
    paths = []
    for entry in sorted(os.listdir(FEATURES_ROOT)):
        fdir = os.path.join(FEATURES_ROOT, entry)
        spec = _resolve_doc(fdir, "spec.md")
        if spec:
            paths.append((entry, spec))
        contract = _resolve_doc(fdir, "contract.md")
        if contract:
            paths.append((entry, contract))
        # Every SKILL.md under skills/*/SKILL.md (any depth-1 skill dir).
        for skill_md in sorted(glob.glob(
                os.path.join(fdir, "skills", "*", "SKILL.md"))):
            paths.append((entry, skill_md))
    return paths


def is_allowlisted(rel_path, line_no, line_text):
    for a_path, a_line, a_substr in ALLOWLIST:
        if a_path == rel_path and a_line == line_no and a_substr in line_text:
            return True
    return False


violations = []
surfaces = feature_doc_surfaces()
for feature, doc_path in surfaces:
    rel_path = os.path.relpath(doc_path, FEATURES_ROOT)
    with open(doc_path) as f:
        for line_no, line in enumerate(f, start=1):
            if PATTERN.search(line):
                if is_allowlisted(rel_path, line_no, line.rstrip("\n")):
                    continue
                violations.append((rel_path, line_no, line.rstrip("\n")))

if violations:
    print("FAIL: historical-burden tags found in feature doc surfaces",
          file=sys.stderr)
    for rel, ln, txt in violations:
        print(f"  {rel}:{ln}: {txt}", file=sys.stderr)
    print(
        f"\n{len(violations)} violation(s). "
        "Scrub tags from feature doc surfaces (preserve in commit messages "
        "and CHANGELOG tombstones), or add to ALLOWLIST after review.",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"PASS: no historical-burden tags in {len(surfaces)} feature doc surfaces "
      f"(spec.md, contract.md, SKILL.md)")
sys.exit(0)
