#!/usr/bin/env python3
"""test-spec-bodies-no-historical-tags.py — CONTRACT-BACKLOG-38 / -40.

Greps every feature's spec.md, contract.md (resolved at specs/<name> —
issue #399 migration complete, fallback dropped #465), and any
skills/*/SKILL.md under each feature for historical-burden patterns that
violate housekeeping protocol criterion #1 (current-design only) and
criterion #2 (no documentation burden).

Two-tier enforcement with per-feature opt-in (Inv 49):

  Baseline tier (enforced on ALL features, unconditionally):
    Plan [A-F]      — cleanup wave / plan identifiers
    BUG-N           — bug item references
    BACKLOG-N       — backlog item references
    Wave N          — wave identifiers

  Strict tier (enforced ONLY on features that have OPTED IN):
    #N              — bare issue/PR references
    per issue/bug/pr — prose pointers (case-insensitive)
    superseded/retired/obsoleted — tombstone language (case-insensitive)

Opt-in is data-driven and per-feature: a feature opts in by declaring
`"housekeeping_clean": true` at the top level of its OWN feature.json.
The checker derives the opt-in set by reading each feature's feature.json
under FEATURES_ROOT (missing/malformed feature.json => not opted in).
No feature declares the flag until its cleanup lands, so introducing the
strict tier is non-breaking: it enforces on nothing until a feature opts
in. CHANGELOG.md is never scanned — only spec.md, contract.md, and
skills/*/SKILL.md are — so feature history relocated to CHANGELOG.md is
exempt by construction.

Such tags belong in commit messages and CHANGELOG.md tombstones, NOT
in feature documentation surfaces. Doc surfaces describe the CURRENT
design; the project ticket that produced any given line is irrelevant
once the line ships.

A hardcoded ALLOWLIST permits legitimate occurrences (algorithm-output
examples whose textual content happens to match the pattern); it applies
to BOTH tiers.

Self-testability: RABBIT_HISTORICAL_TAGS_FEATURES_ROOT overrides the
features root, and RABBIT_HISTORICAL_TAGS_CLEANED (comma-separated
feature names), when set, REPLACES the feature.json-derived opt-in set
(empty string => empty set), so a companion test can point the checker
at fixture feature trees. Absent the overrides the checker behaves
exactly as the production check (real features root; opt-in read from
each feature's feature.json housekeeping_clean flag).

Non-interactive. Exits non-zero on any unallowlisted match.
"""

import glob
import json
import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.environ.get(
    "RABBIT_HISTORICAL_TAGS_FEATURES_ROOT",
    os.path.join(REPO_ROOT, ".claude", "features"),
)

BASELINE_PATTERN = re.compile(r"Plan [A-F]|BUG-[0-9]|BACKLOG-[0-9]|Wave [0-9]")
STRICT_PATTERN = re.compile(
    r"#[0-9]+|per (issue|bug|pr)\b|superseded|retired|obsoleted",
    re.IGNORECASE,
)

# The strict-tier opt-in set is data-driven: a feature opts in by setting
# top-level "housekeeping_clean": true in its OWN feature.json. The set is
# derived by reading every feature's feature.json under FEATURES_ROOT.
def derive_cleaned_features():
    """Return the set of feature names whose feature.json declares
    top-level "housekeeping_clean": true. Missing or malformed feature.json
    => not opted in."""
    cleaned = set()
    for entry in sorted(os.listdir(FEATURES_ROOT)):
        fjson = os.path.join(FEATURES_ROOT, entry, "feature.json")
        try:
            with open(fjson) as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("housekeeping_clean") is True:
            cleaned.add(entry)
    return cleaned


_cleaned_override = os.environ.get("RABBIT_HISTORICAL_TAGS_CLEANED")
if _cleaned_override is not None:
    # Override REPLACES the feature.json-derived set (fixture hermeticity).
    CLEANED_FEATURES = {
        name.strip() for name in _cleaned_override.split(",") if name.strip()
    }
else:
    CLEANED_FEATURES = derive_cleaned_features()

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
    # contract Inv 36 — the literal `status` enum value "retired" and its
    # documented retirement semantics. "retired" here is a live design
    # term (the feature-status API value), not a historical-burden tag.
    ("contract/specs/spec.md", 139, "retired"),
    ("contract/specs/spec.md", 140, "retired"),
    ("contract/specs/spec.md", 141, "retired"),
    ("contract/specs/spec.md", 142, "retired"),
    # contract Inv 49 — the strict-tier pattern DEFINITIONS. These lines
    # quote the regex (`#[0-9]+`) and the tombstone-word vocabulary
    # (`superseded`, `retired`, `obsoleted`) that the check itself rejects;
    # they are algorithm-spec samples, not historical references.
    ("contract/specs/spec.md", 185, "#[0-9]+"),
    ("contract/specs/spec.md", 186, "superseded"),
    ("contract/specs/spec.md", 187, "obsoleted"),
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
    # Baseline tier applies to every feature; the strict tier additionally
    # applies only to features that have opted in via CLEANED_FEATURES.
    patterns = [BASELINE_PATTERN]
    if feature in CLEANED_FEATURES:
        patterns.append(STRICT_PATTERN)
    with open(doc_path) as f:
        for line_no, line in enumerate(f, start=1):
            if any(p.search(line) for p in patterns):
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
