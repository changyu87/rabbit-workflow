#!/usr/bin/env python3
"""Inv 6: spec-path layout resolves to the canonical flat docs/ only.

Source-inspection test over BOTH spec-lifecycle SKILL.md bodies and the
rabbit-spec-creator agent body. Every rabbit feature carries the flat docs/
layout (docs/spec.md, docs/contract.md); there is no specs/ or legacy
docs/spec/ fallback. The skills that resolve ANY feature's spec path MUST
target the canonical flat docs/spec.md ONLY and MUST NOT describe any
specs/spec.md or docs/spec/spec.md fallback.

Asserts:
  rabbit-spec-update SKILL.md
    - mentions the canonical flat docs/spec.md path
    - does NOT mention the specs/spec.md fallback path
    - does NOT mention the legacy docs/spec/spec.md fallback path
  rabbit-spec-create SKILL.md
    - mentions the canonical flat docs/spec.md destination for new specs
    - does NOT mention the specs/spec.md fallback path
    - does NOT mention the legacy docs/spec/spec.md path
  rabbit-spec-creator agent
    - names the flat docs/spec.md target
    - does NOT name the legacy docs/spec/spec.md target

Also asserts rabbit-spec ITSELF carries the flat docs/ layout:
  - rabbit-spec/docs/spec.md and docs/contract.md exist
  - no legacy rabbit-spec/specs/ directory remains

Run non-interactively. Exits non-zero on failure.

Version: 3.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
that supersede this feature.
"""
from __future__ import annotations

import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
UPDATE_MD = FEATURE_DIR / "skills/rabbit-spec-update/SKILL.md"
CREATE_MD = FEATURE_DIR / "skills/rabbit-spec-create/SKILL.md"
CREATOR_AGENT = FEATURE_DIR / "agents/rabbit-spec-creator.md"


def _text(p: Path) -> str:
    assert p.exists(), f"missing file: {p}"
    return p.read_text()


def test_update_targets_canonical_only() -> None:
    text = _text(UPDATE_MD)
    assert "docs/spec.md" in text, (
        "rabbit-spec-update SKILL.md must name the canonical flat "
        "'docs/spec.md' path"
    )
    assert "specs/spec.md" not in text, (
        "rabbit-spec-update SKILL.md must NOT describe the dead "
        "'specs/spec.md' fallback path"
    )
    assert "docs/spec/spec.md" not in text, (
        "rabbit-spec-update SKILL.md must NOT describe the dead legacy "
        "'docs/spec/spec.md' fallback path"
    )


def test_create_targets_canonical_only() -> None:
    text = _text(CREATE_MD)
    assert "docs/spec.md" in text, (
        "rabbit-spec-create SKILL.md must name the canonical flat "
        "'docs/spec.md' destination"
    )
    assert "specs/spec.md" not in text, (
        "rabbit-spec-create SKILL.md must NOT describe the dead "
        "'specs/spec.md' fallback path"
    )
    assert "docs/spec/spec.md" not in text, (
        "rabbit-spec-create SKILL.md must NOT describe the dead legacy "
        "'docs/spec/spec.md' fallback path"
    )


def test_creator_agent_targets_canonical_only() -> None:
    text = _text(CREATOR_AGENT)
    assert "docs/spec.md" in text, (
        "rabbit-spec-creator agent must name the flat 'docs/spec.md' target"
    )
    assert "docs/spec/spec.md" not in text, (
        "rabbit-spec-creator agent must NOT name the legacy "
        "'docs/spec/spec.md' target"
    )


def test_rabbit_spec_self_on_docs() -> None:
    assert (FEATURE_DIR / "docs" / "spec.md").exists(), (
        "rabbit-spec must carry docs/spec.md"
    )
    assert (FEATURE_DIR / "docs" / "contract.md").exists(), (
        "rabbit-spec must carry docs/contract.md"
    )
    assert not (FEATURE_DIR / "specs").is_dir(), (
        "rabbit-spec must not retain a legacy specs/ directory"
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
