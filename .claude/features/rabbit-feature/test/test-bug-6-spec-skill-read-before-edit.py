#!/usr/bin/env python3
"""E2E regression test for RABBIT-FEATURE-BUG-6 / Inv 35.

Asserts the `rabbit-feature-spec` SKILL.md encodes the
Read-comprehend-Write contract mandated by Inv 35:

- Step 1 (Read Current State) contains a hard `MUST Read` mandate that
  references the target spec.md.
- Step 4 (Update the Spec) contains a `PRE-CONDITION` note that
  references the Read obligation from Step 1.

Rationale: in practice, omitting the Read step caused repeated
`File must be read first` tool errors. The mandate must appear in
both Step 1 (forward-looking instruction) and Step 4 (defensive
pre-condition for callers that arrive at edit time without having
read).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When Claude Code's per-session
file-state guard for Edits is removed, or when the
rabbit-feature-spec skill is fundamentally restructured.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_MD = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-spec/SKILL.md"
)


def _extract_section(text: str, heading_re: str) -> str:
    """Return the body of a `## ...` section up to the next `## ` heading."""
    m = re.search(
        rf"^##\s+{heading_re}\s*$(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, f"SKILL.md is missing a section matching '## {heading_re}'"
    return m.group(1)


def test_step_1_has_must_read_mandate() -> None:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    body = _extract_section(SKILL_MD.read_text(), r"Step 1.*Read Current State")

    assert "MUST Read" in body, (
        "Step 1 must contain the hard mandate 'MUST Read' "
        "(case-sensitive, capital R) for the target spec.md"
    )
    assert "spec.md" in body, (
        "Step 1 must reference 'spec.md' as the target of the Read mandate"
    )

    # The MUST Read clause must mention spec.md in close proximity
    # (within ~200 chars) so the mandate actually binds Read to spec.md.
    must_pos = body.find("MUST Read")
    spec_pos = body.find("spec.md", must_pos)
    assert spec_pos != -1 and (spec_pos - must_pos) < 300, (
        "the 'MUST Read' mandate must reference spec.md nearby "
        f"(MUST Read at {must_pos}, next spec.md at {spec_pos})"
    )


def test_step_4_has_pre_condition_note() -> None:
    body = _extract_section(SKILL_MD.read_text(), r"Step 4.*Update the Spec")

    assert "PRE-CONDITION" in body, (
        "Step 4 must contain a 'PRE-CONDITION' note about the Read obligation"
    )

    # The pre-condition must reference the Read obligation.
    pre_pos = body.find("PRE-CONDITION")
    tail = body[pre_pos:pre_pos + 600]
    assert "Read" in tail, (
        "Step 4 PRE-CONDITION note must reference the Read obligation"
    )


def main() -> int:
    tests = [
        test_step_1_has_must_read_mandate,
        test_step_4_has_pre_condition_note,
    ]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
