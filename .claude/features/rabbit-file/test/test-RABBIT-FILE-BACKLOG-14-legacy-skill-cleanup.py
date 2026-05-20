#!/usr/bin/env python3
"""Retirement-explicit phrasing test for rabbit-file (BACKLOG-14 addendum).

The bare phrasing "Replaces rabbit-bug and rabbit-backlog" reads as if the
legacy skills still exist as alternatives, which tripped a fresh session
into calling Skill("rabbit-backlog") and erroring. This test asserts the
bare phrasing is gone and retirement-explicit phrasing appears at all four
metadata sites:

  1) feature.json  -> top-level `summary`
  2) docs/spec/spec.md  -> Purpose paragraph
  3) docs/spec/contract.md  -> provides.skills[].description
  4) skills/rabbit-file/SKILL.md  -> frontmatter description
"""
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).parent.parent
TARGETS = {
    "feature.json": FEATURE_DIR / "feature.json",
    "spec.md": FEATURE_DIR / "docs" / "spec" / "spec.md",
    "contract.md": FEATURE_DIR / "docs" / "spec" / "contract.md",
    "SKILL.md": FEATURE_DIR / "skills" / "rabbit-file" / "SKILL.md",
}

BARE_PHRASE = "Replaces rabbit-bug and rabbit-backlog"
RETIREMENT_SIGNALS = ("no longer exist", "sole entry point")

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


for label, path in TARGETS.items():
    if not path.is_file():
        assert_fail(f"{label} exists", f"missing at {path}")
        continue
    txt = path.read_text()

    # The bare phrasing — without any retirement qualifier on the same line —
    # MUST NOT appear. We allow the phrase only if followed (on the same
    # logical chunk) by a retirement signal like "(and retires)" or
    # "no longer exist".
    bare_hits = []
    for line_no, line in enumerate(txt.splitlines(), start=1):
        if BARE_PHRASE in line:
            # The legacy bare form, e.g. "Replaces rabbit-bug and rabbit-backlog."
            # is bad. The retirement-explicit form
            # "Replaces (and retires) the legacy rabbit-bug and rabbit-backlog"
            # does NOT match BARE_PHRASE because of "(and retires) the legacy "
            # between "Replaces" and "rabbit-bug". So any hit is a real bare hit.
            bare_hits.append((line_no, line.strip()))

    if not bare_hits:
        assert_pass(f"{label} does not contain bare 'Replaces rabbit-bug and rabbit-backlog' phrasing")
    else:
        assert_fail(
            f"{label} does not contain bare 'Replaces rabbit-bug and rabbit-backlog' phrasing",
            f"found at line(s): {bare_hits}",
        )

    missing_signals = [s for s in RETIREMENT_SIGNALS if s not in txt]
    if not missing_signals:
        assert_pass(f"{label} contains retirement-explicit signals {RETIREMENT_SIGNALS}")
    else:
        assert_fail(
            f"{label} contains retirement-explicit signals {RETIREMENT_SIGNALS}",
            f"missing: {missing_signals}",
        )

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
