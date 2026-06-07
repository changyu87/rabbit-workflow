#!/usr/bin/env python3
"""#688: dead stage/relocation narration MUST NOT survive on live surfaces.

Housekeeping round 2 (under #639 prove-it-dead-or-flag). rabbit-spec's
predecessor features have all landed or been removed: the `spec-seeder`
and `rabbit-feature-spec` feature directories no longer exist, both
spec-lifecycle skills are present on disk, and `rabbit-feature-scaffold`
exists. The "After Stage 2 it hosts ... Stage 3 will add ... absorbs the
former <X> feature" forward-looking relocation narration is therefore dead
and was removed from docs/spec.md. This is an end-to-end content guard
asserting that dead narration does not reappear on the live spec surface.

The bans below target the dead narration ONLY. A bare present-tense
mention of the absorbed lineage in feature.json's summary is allowed
(it is current ownership fact, not stage narration).

Verification anchoring (each ban traces to a #639 check):
  - `spec-seeder` directory absent  -> grep for the phrase is dead.
  - `rabbit-feature-spec` directory absent -> "Stage N will add" is dead.
  - both skills on disk -> "After Stage 2 it hosts" future framing is dead.

Static check; does not exercise runtime behaviour.

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

# Dead stage/relocation narration patterns banned on docs/spec.md.
BANNED = (
    re.compile(r"After Stage\b", re.IGNORECASE),
    re.compile(r"Stage \d+ will add", re.IGNORECASE),
    re.compile(r"absorbs the behavior of the former", re.IGNORECASE),
    re.compile(r"absorbs and subagent-ifies", re.IGNORECASE),
    re.compile(r"\bin Stage \d+\)", re.IGNORECASE),
)


def test_spec_has_no_dead_stage_narration() -> None:
    assert SPEC_MD.is_file(), f"missing spec.md: {SPEC_MD}"
    text = SPEC_MD.read_text()
    offenders: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for pat in BANNED:
            if pat.search(line):
                offenders.append(f"  L{lineno}: {line.strip()!r}")
                break
    assert not offenders, (
        "docs/spec.md must not carry dead stage/relocation narration "
        "(#688 / #639). Offending lines:\n" + "\n".join(offenders)
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
