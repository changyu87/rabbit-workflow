#!/usr/bin/env python3
"""#816: restated downstream/mechanism rationale MUST NOT survive on spec.md.

Measured-reduction wave (child of #794, prove-it-dead-or-flag, coding-rules
§6/§2/§7). Inv 3(b) and Inv 3(e) each carried a block of rationale that is a
verbatim restatement of content the spec already points at:

  - Inv 3(b)'s "the dropped count is consumed by rabbit-spec-create Step 4 so
    the user is told 'and M dropped' ..." restates the downstream consumption
    that rabbit-spec-create/SKILL.md Step 4 already owns. The load-bearing
    behaviour (emit a non-silent stderr NOTE naming the dropped count; silent
    at/below cap) stays; only the downstream-consumption restatement was cut.

  - Inv 3(e)'s parents[0..4] path-arithmetic enumeration and the "forbidden
    because ... resolve to the user-project root" expansion restate the inline
    comment in scripts/dispatch-spec-create.py. The load-bearing constraint
    (resolve via Path(__file__).resolve().parents[4]; NOT git rev-parse, NOT
    os.getcwd(); plugin-mode reason; "Enforced by 3 tests") stays; only the
    doubled arithmetic + expanded rationale was cut.

This is an end-to-end content guard asserting the removed restatement does not
reappear on the live spec surface. Static check; no runtime behaviour.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-spec is retired
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"

# Restated rationale removed in the #816 measured-reduction wave.
BANNED = (
    # Inv 3(b) downstream-consumption restatement (owned by SKILL.md Step 4).
    re.compile(r"dropped count is consumed by", re.IGNORECASE),
    # Inv 3(e) parents[0..4] path-arithmetic enumeration (owned by the script
    # comment).
    re.compile(r"parents\[0\]\s*=\s*scripts", re.IGNORECASE),
    # Inv 3(e) expanded forbidden-mechanism rationale (owned by the script
    # comment).
    re.compile(r"resolve to the user-project root", re.IGNORECASE),
)

# Load-bearing tokens that MUST remain (zero-behavior-loss guard).
REQUIRED = (
    "dropped",                                 # Inv 3(b) NOTE behaviour
    "Path(__file__).resolve().parents[4]",     # Inv 3(e) constraint
    "git rev-parse",                           # Inv 3(e) forbidden mechanism
    "os.getcwd()",                             # Inv 3(e) forbidden mechanism
    "test-dispatch-truncation-not-silent.py",  # Inv 3(b) enforcing test
)


def test_spec_has_no_restated_rationale() -> None:
    assert SPEC_MD.is_file(), f"missing spec.md: {SPEC_MD}"
    text = SPEC_MD.read_text()
    offenders: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for pat in BANNED:
            if pat.search(line):
                offenders.append(f"  L{lineno}: {line.strip()!r}")
                break
    assert not offenders, (
        "docs/spec.md must not carry restated downstream/mechanism rationale "
        "(#816). Offending lines:\n" + "\n".join(offenders)
    )


def test_spec_keeps_load_bearing_tokens() -> None:
    assert SPEC_MD.is_file(), f"missing spec.md: {SPEC_MD}"
    text = SPEC_MD.read_text()
    missing = [tok for tok in REQUIRED if tok not in text]
    assert not missing, (
        "docs/spec.md lost load-bearing tokens during reduction (#816): "
        + ", ".join(missing)
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
