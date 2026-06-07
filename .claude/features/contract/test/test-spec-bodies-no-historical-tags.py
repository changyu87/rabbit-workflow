#!/usr/bin/env python3
"""test-spec-bodies-no-historical-tags.py — CONTRACT-BACKLOG-38 / -40.

Greps every feature's spec.md, contract.md (resolved through the canonical
dual-read resolver in lib/checks.py — flat docs/<name> preferred, specs/<name>
fallback), and any skills/*/SKILL.md under each feature for historical-burden
patterns that violate housekeeping protocol criterion #1 (current-design only)
and criterion #2 (no documentation burden).

Routing resolution through lib/checks.py keeps a feature UNDER enforcement on
EITHER layout: a feature whose spec.md/contract.md has been moved to the flat
docs/ layout is still scanned, closing the false-green class where a migrated
feature silently dropped out of the scan.

Two-tier enforcement with per-feature opt-in (Inv 41):

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

Allowlist matching is CONTENT-keyed, not line-number-keyed (#696). Each
allowlist entry is `(feature, logical_doc, content_substring)`; an
occurrence is allowed when the flagged line CONTAINS `content_substring`,
regardless of the line number it lands on. The previous scheme pinned each
entry to an ABSOLUTE line number in another feature's spec, so any
housekeeping line removal/insertion in that spec shifted the pinned line
and reddened this cross-feature gate even though the allowed content was
unchanged (this blocked #695). Content-keying delinks the gate from
cross-feature line counts.

Self-testability: RABBIT_HISTORICAL_TAGS_FEATURES_ROOT overrides the
features root, and RABBIT_HISTORICAL_TAGS_CLEANED (comma-separated
feature names), when set, REPLACES the feature.json-derived opt-in set
(empty string => empty set), so a companion test can point the checker
at fixture feature trees. RABBIT_HISTORICAL_TAGS_ALLOWLIST, when set,
ADDS fixture allowlist entries to the production ALLOWLIST (it never
replaces it): the value is a newline-or-semicolon-separated list of
`feature:logical_doc:line:substring` records. The 4-field record shape is
retained for backward compatibility, but the `line` field is accepted and
IGNORED for matching (matching is content-keyed); only
`(feature, logical_doc, substring)` is used. A hermetic test can thus
assert allowlist suppression (applies to BOTH tiers per Inv 60) without
editing the live production allowlist. Absent the overrides the checker
behaves exactly as the production check (real features root; opt-in read
from each feature's feature.json housekeeping_clean flag; production
ALLOWLIST unchanged).

Non-interactive. Exits non-zero on any unallowlisted match.
"""

import glob
import importlib.util
import json
import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))


def _load_resolve_spec_path():
    """Load the canonical resolve_spec_path from lib/checks.py so spec-body
    scanning uses the SAME dual-read resolution as the contract validators
    (flat docs/<name> preferred, specs/<name> fallback). Avoids each scanner
    re-implementing a divergent _resolve_doc."""
    checks_path = os.path.join(FEATURE_DIR, "lib", "checks.py")
    spec = importlib.util.spec_from_file_location(
        "contract_lib_checks_histtags", checks_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.resolve_spec_path


resolve_spec_path = _load_resolve_spec_path()
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

# (feature, logical_doc, content_substring) tuples — CONTENT-keyed (#696).
# Each entry records a legitimate occurrence and WHY it is permitted. An
# occurrence is allowed when its line CONTAINS content_substring; the line
# NUMBER is deliberately not part of the key, so housekeeping line shifts in
# a feature's spec do not redden this cross-feature gate. Update only after
# manual review confirms the line is not a project tag but a genuine value
# (e.g. algorithm-output sample).
#
# The key uses the LOGICAL doc name (the path relative to the feature dir
# with the leading docs/ or specs/ layout prefix stripped: "spec.md",
# "contract.md", or "skills/<name>/SKILL.md"), NOT a layout-pinned
# "specs/..." / "docs/..." string. An entry therefore stays live after a
# feature migrates between the specs/ and docs/ layouts — no dead keys.
#
# content_substring MUST be specific enough to identify the intended
# occurrence without matching unrelated lines in the same surface (it is the
# only disambiguator now that line numbers are gone).
ALLOWLIST = {
    # contract Inv 28 — the literal `status` enum value "retired" and its
    # documented retirement semantics. "retired" here is a live design
    # term (the feature-status API value), not a historical-burden tag.
    # The substrings pin the specific Inv 28 enum-semantics sentences.
    ("contract", "spec.md", '(default when omitted) or `"retired"`'),
    ("contract", "spec.md", 'enum: ["active", "retired"]'),
    ("contract", "spec.md", "exit 0 with a `RETIRED:` notice"),
    ("contract", "spec.md", "MUST mark retired features"),
    # contract Inv 41 — the strict-tier pattern DEFINITIONS. These lines
    # quote the regex (`#[0-9]+`) and the tombstone-word vocabulary
    # (`superseded`, `retired`, `obsoleted`) that the check itself rejects;
    # they are algorithm-spec samples, not historical references.
    ("contract", "spec.md", "(`#[0-9]+`), `per issue`"),
    ("contract", "spec.md", "tombstone language (`superseded`, `retired`,"),
    ("contract", "spec.md", "`obsoleted`, case-insensitive)"),
    # rabbit-auto-evolve Inv 19 / contract Inv 28 — the literal `status`
    # enum value "retired". rabbit-auto-evolve's spec.md documents
    # triage-issue.py's verbatim `status == "retired"` check (feature.json
    # status enum) on the Inv 19 triage decision-table row
    # (`feature.json.status == "retired"` -> `close-not-planned` /
    # `feature-retired`); the row names the load-bearing literal value the
    # triage interpreter checks verbatim plus the `feature-retired` reason
    # code. It is a live status-enum literal, not a historical-burden
    # tombstone, and cannot be reworded without making the spec inaccurate.
    # Mirrors the contract OWN-spec retired-enum precedent above (#556 / #634).
    ("rabbit-auto-evolve", "spec.md", 'feature.json.status == "retired"'),
}


def _parse_allowlist_override(raw):
    """Parse the RABBIT_HISTORICAL_TAGS_ALLOWLIST override value (Inv 60).

    The value is a newline-or-semicolon-separated list of
    `feature:logical_doc:line:substring` records. The 4-field record shape
    is retained for backward compatibility, but matching is CONTENT-keyed
    (#696): the `line` field is parsed and DISCARDED — only
    (feature, logical_doc, substring) is added to the allowlist. Each record
    is split on the FIRST three colons only, so a substring containing `:`
    is preserved verbatim. Malformed records (fewer than four fields, or a
    non-integer line) are skipped silently — the override exists only for
    fixture tests, which supply well-formed records.

    Returns a set of (feature, logical_doc, substring) tuples to ADD to the
    production ALLOWLIST.
    """
    extra = set()
    for record in re.split(r"[;\n]", raw):
        record = record.strip()
        if not record:
            continue
        parts = record.split(":", 3)
        if len(parts) != 4:
            continue
        feature, logical_doc, line_s, substr = parts
        try:
            int(line_s)  # validated for format compatibility, then ignored
        except ValueError:
            continue
        extra.add((feature, logical_doc, substr))
    return extra


_allowlist_override = os.environ.get("RABBIT_HISTORICAL_TAGS_ALLOWLIST")
if _allowlist_override is not None:
    # Override ADDS fixture entries to the production ALLOWLIST (never
    # replaces it) so a hermetic test can assert allowlist suppression
    # without editing the live production allowlist.
    ALLOWLIST = ALLOWLIST | _parse_allowlist_override(_allowlist_override)


def _resolve_doc(fdir, name):
    """Resolve a feature's spec.md/contract.md via the canonical dual-read
    resolver (flat docs/<name> preferred, specs/<name> fallback). Returns
    the existing path or None."""
    path = resolve_spec_path(fdir, name)
    if os.path.isfile(path):
        return path
    return None


def _logical_doc(feature, doc_path):
    """Return the layout-independent doc key for an absolute surface path:
    the path relative to the feature dir with the leading docs/ or specs/
    layout prefix stripped. e.g. .../tdd-subagent/docs/spec.md -> "spec.md";
    .../foo/skills/bar/SKILL.md -> "skills/bar/SKILL.md"."""
    fdir = os.path.join(FEATURES_ROOT, feature)
    rel = os.path.relpath(doc_path, fdir)
    for prefix in ("docs" + os.sep, "specs" + os.sep):
        if rel.startswith(prefix):
            return rel[len(prefix):]
    return rel


def feature_doc_surfaces():
    """Yield (feature_name, abs_path) for every monitored doc surface:
    spec.md, contract.md (each resolved via the dual-read resolver), and
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


def is_allowlisted(feature, logical_doc, line_text):
    """Content-keyed allowlist match (#696): an occurrence is allowed when,
    for its (feature, logical_doc), some ALLOWLIST entry's content_substring
    appears in the line text. There is deliberately NO line-number argument,
    so a legitimate occurrence stays allowed wherever the line lands."""
    for a_feature, a_doc, a_substr in ALLOWLIST:
        if (a_feature == feature and a_doc == logical_doc
                and a_substr in line_text):
            return True
    return False


violations = []
surfaces = feature_doc_surfaces()
for feature, doc_path in surfaces:
    rel_path = os.path.relpath(doc_path, FEATURES_ROOT)
    logical_doc = _logical_doc(feature, doc_path)
    # Baseline tier applies to every feature; the strict tier additionally
    # applies only to features that have opted in via CLEANED_FEATURES.
    patterns = [BASELINE_PATTERN]
    if feature in CLEANED_FEATURES:
        patterns.append(STRICT_PATTERN)
    with open(doc_path) as f:
        for line_no, line in enumerate(f, start=1):
            if any(p.search(line) for p in patterns):
                if is_allowlisted(feature, logical_doc, line.rstrip("\n")):
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
