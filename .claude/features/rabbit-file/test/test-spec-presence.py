#!/usr/bin/env python3
"""Presence and metadata tests for rabbit-file spec.md and surrounding docs.

Covers three spec-side invariants:

  1. spec.md MUST carry YAML frontmatter with feature, version, owner,
     deprecation_criterion (spec-rules.md §3).

  2. spec.md MUST contain an ## Operational characteristics section
     documenting the worst-case push-attempt budget (48 attempts) and
     wall-time envelope (~30s) implied by the 16-retry invariant.

  3. The retirement-explicit phrasing for the legacy rabbit-bug and
     rabbit-backlog skills MUST appear at all four metadata sites
     (feature.json, spec.md, contract.md, SKILL.md) so a fresh session
     does not mistakenly invoke the retired skills.
"""
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).parent.parent
SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

pass_ = 0
fail = 0


def assert_pass(msg):
    global pass_
    print(f"PASS: {msg}")
    pass_ += 1


def assert_fail(msg, reason):
    global fail
    print(f"FAIL: {msg} - {reason}")
    fail += 1


# ---------------------------------------------------------------------------
# (1) spec.md frontmatter
# ---------------------------------------------------------------------------

REQUIRED_FM_KEYS = ["feature", "version", "owner", "deprecation_criterion"]

if not SPEC_MD.is_file():
    assert_fail("spec.md exists", f"missing at {SPEC_MD}")
    spec_txt = ""
else:
    spec_txt = SPEC_MD.read_text()
    fm_match = re.match(r"^---\n(.*?)\n---\n", spec_txt, re.DOTALL)
    if not fm_match:
        assert_fail(
            "spec.md has YAML frontmatter",
            "no leading --- ... --- block found",
        )
    else:
        fm = fm_match.group(1)
        missing = [k for k in REQUIRED_FM_KEYS
                   if not re.search(rf"^{k}:", fm, re.MULTILINE)]
        if missing:
            assert_fail(
                "spec.md frontmatter has all required keys",
                f"missing keys: {missing}",
            )
        else:
            assert_pass(
                "spec.md frontmatter has feature/version/owner/"
                "deprecation_criterion"
            )

# ---------------------------------------------------------------------------
# (2) Operational characteristics section
# ---------------------------------------------------------------------------

if spec_txt:
    if "## Operational characteristics" in spec_txt:
        assert_pass("spec.md has ## Operational characteristics section")
    else:
        assert_fail(
            "spec.md has ## Operational characteristics section",
            "section header not found",
        )

    if "48 push attempts" in spec_txt:
        assert_pass("spec.md documents 48 push-attempt worst case")
    else:
        assert_fail(
            "spec.md documents 48 push-attempt worst case",
            "'48 push attempts' string not found",
        )

    if "~30s" in spec_txt:
        assert_pass("spec.md documents ~30s wall-time worst case")
    else:
        assert_fail(
            "spec.md documents ~30s wall-time worst case",
            "'~30s' string not found",
        )

# ---------------------------------------------------------------------------
# (3) Retirement-explicit phrasing at all four metadata sites
# ---------------------------------------------------------------------------

TARGETS = {
    "feature.json": FEATURE_DIR / "feature.json",
    "spec.md": FEATURE_DIR / "docs" / "spec" / "spec.md",
    "contract.md": FEATURE_DIR / "docs" / "spec" / "contract.md",
    "SKILL.md": FEATURE_DIR / "skills" / "rabbit-file" / "SKILL.md",
}

BARE_PHRASE = "Replaces rabbit-bug and rabbit-backlog"
RETIREMENT_SIGNALS = ("no longer exist", "sole entry point")

for label, path in TARGETS.items():
    if not path.is_file():
        assert_fail(f"{label} exists", f"missing at {path}")
        continue
    txt = path.read_text()

    bare_hits = []
    for line_no, line in enumerate(txt.splitlines(), start=1):
        if BARE_PHRASE in line:
            bare_hits.append((line_no, line.strip()))

    if not bare_hits:
        assert_pass(
            f"{label} does not contain bare 'Replaces rabbit-bug and "
            f"rabbit-backlog' phrasing"
        )
    else:
        assert_fail(
            f"{label} does not contain bare 'Replaces rabbit-bug and "
            f"rabbit-backlog' phrasing",
            f"found at line(s): {bare_hits}",
        )

    missing_signals = [s for s in RETIREMENT_SIGNALS if s not in txt]
    if not missing_signals:
        assert_pass(
            f"{label} contains retirement-explicit signals "
            f"{RETIREMENT_SIGNALS}"
        )
    else:
        assert_fail(
            f"{label} contains retirement-explicit signals "
            f"{RETIREMENT_SIGNALS}",
            f"missing: {missing_signals}",
        )


print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
