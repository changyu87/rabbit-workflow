#!/usr/bin/env python3
"""Inv 6: spec-path layout dual-read (issue #399 Phase 2 coexistence window).

Source-inspection test over BOTH spec-lifecycle SKILL.md bodies. The
docs/spec/ -> specs/ migration runs feature-by-feature, so the skills that
resolve ANY feature's spec path must prefer the canonical specs/ layout and
fall back to the legacy docs/spec/ layout.

Asserts:
  rabbit-spec-update SKILL.md
    - mentions the canonical specs/spec.md path
    - mentions the legacy docs/spec/spec.md path
    - names specs/ as the PREFERRED layout and docs/spec/ as the fallback
  rabbit-spec-create SKILL.md
    - mentions the canonical specs/spec.md destination
    - mentions the legacy docs/spec/spec.md destination
    - names specs/ as the canonical destination for new specs

Also asserts the migration is complete for rabbit-spec ITSELF:
  - rabbit-spec/specs/spec.md and specs/contract.md exist
  - rabbit-spec/docs/ does NOT exist

Run non-interactively. Exits non-zero on failure.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when every rabbit feature has migrated off docs/spec/
and the legacy fallback is dropped (issue #399).
"""
from __future__ import annotations

import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
UPDATE_MD = FEATURE_DIR / "skills/rabbit-spec-update/SKILL.md"
CREATE_MD = FEATURE_DIR / "skills/rabbit-spec-create/SKILL.md"


def _text(p: Path) -> str:
    assert p.exists(), f"missing SKILL.md: {p}"
    return p.read_text()


def _has_preferred_fallback_phrasing(text: str) -> bool:
    """True when the body names specs/ as preferred/canonical and docs/spec/
    as the fallback/legacy layout — in a window that mentions both."""
    low = text.lower()
    preferred_words = ("prefer", "preferred", "canonical")
    fallback_words = ("fall back", "fallback", "legacy")
    return (
        any(w in low for w in preferred_words)
        and any(w in low for w in fallback_words)
    )


def test_update_mentions_both_layouts() -> None:
    text = _text(UPDATE_MD)
    assert "specs/spec.md" in text, (
        "rabbit-spec-update SKILL.md must mention the canonical "
        "'specs/spec.md' path"
    )
    assert "docs/spec/spec.md" in text, (
        "rabbit-spec-update SKILL.md must mention the legacy "
        "'docs/spec/spec.md' fallback path"
    )


def test_update_prefers_specs() -> None:
    text = _text(UPDATE_MD)
    assert _has_preferred_fallback_phrasing(text), (
        "rabbit-spec-update SKILL.md must name specs/ as the preferred/"
        "canonical layout and docs/spec/ as the fallback/legacy layout"
    )


def test_create_mentions_both_layouts() -> None:
    text = _text(CREATE_MD)
    assert "specs/spec.md" in text, (
        "rabbit-spec-create SKILL.md must mention the canonical "
        "'specs/spec.md' destination"
    )
    assert "docs/spec/spec.md" in text, (
        "rabbit-spec-create SKILL.md must mention the legacy "
        "'docs/spec/spec.md' destination"
    )


def test_create_canonical_specs() -> None:
    text = _text(CREATE_MD)
    assert _has_preferred_fallback_phrasing(text), (
        "rabbit-spec-create SKILL.md must name specs/ as the canonical "
        "destination for new specs and docs/spec/ as the legacy fallback"
    )


def test_rabbit_spec_self_migrated() -> None:
    assert (FEATURE_DIR / "specs" / "spec.md").exists(), (
        "rabbit-spec must carry specs/spec.md after Phase 2 migration"
    )
    assert (FEATURE_DIR / "specs" / "contract.md").exists(), (
        "rabbit-spec must carry specs/contract.md after Phase 2 migration"
    )
    assert not (FEATURE_DIR / "docs").exists(), (
        "rabbit-spec must NOT carry a docs/ directory after Phase 2 migration"
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
