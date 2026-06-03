#!/usr/bin/env python3
"""Inv 6: spec-path layout dual-read (issue #399 Phase 2a coexistence window).

Source-inspection test over BOTH spec-lifecycle SKILL.md bodies and the
rabbit-spec-creator agent body. The specs/ -> flat docs/ migration runs
feature-by-feature, so the skills that resolve ANY feature's spec path must
PREFER the flat docs/ layout (docs/spec.md, docs/contract.md), FALL BACK to
the specs/ layout (specs/spec.md, specs/contract.md), and still recognize the
legacy docs/spec/ layout (docs/spec/spec.md) in place.

Asserts:
  rabbit-spec-update SKILL.md
    - mentions the preferred flat docs/spec.md path
    - mentions the specs/spec.md fallback path
    - mentions the legacy docs/spec/spec.md fallback path
    - names docs/ as the PREFERRED layout (preferred/canonical) with
      specs/ + docs/spec/ as the fallback/legacy layouts
  rabbit-spec-create SKILL.md
    - mentions the canonical flat docs/spec.md destination for new specs
    - mentions the specs/spec.md fallback path
    - mentions the legacy docs/spec/spec.md path
    - names flat docs/ as the canonical destination for new specs with
      specs/ + docs/spec/ recognized as existing-layout fallbacks
  rabbit-spec-creator agent
    - names the flat docs/spec.md target (not the legacy docs/spec/spec.md
      as its sole target)

Also asserts rabbit-spec ITSELF stays on specs/ during Phase 2a (no files
move yet; the repo is all on specs/ so the fallback hits and tests stay
green):
  - rabbit-spec/specs/spec.md and specs/contract.md exist

Run non-interactively. Exits non-zero on failure.

Version: 2.0.0
Owner: rabbit-workflow team
Deprecation criterion: when every rabbit feature has migrated onto the flat
docs/ layout and the specs/ + docs/spec/ fallbacks are dropped (issue #399).
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


def _names_flat_docs_preferred(text: str) -> bool:
    """True when the body names the flat docs/ layout as preferred/canonical
    and the specs/ (and legacy docs/spec/) layout as the fallback/legacy."""
    low = text.lower()
    preferred_words = ("prefer", "preferred", "canonical")
    fallback_words = ("fall back", "fallback", "legacy")
    return (
        any(w in low for w in preferred_words)
        and any(w in low for w in fallback_words)
    )


def test_update_mentions_all_layouts() -> None:
    text = _text(UPDATE_MD)
    assert "docs/spec.md" in text, (
        "rabbit-spec-update SKILL.md must mention the preferred flat "
        "'docs/spec.md' path"
    )
    assert "specs/spec.md" in text, (
        "rabbit-spec-update SKILL.md must mention the 'specs/spec.md' "
        "fallback path"
    )
    assert "docs/spec/spec.md" in text, (
        "rabbit-spec-update SKILL.md must mention the legacy "
        "'docs/spec/spec.md' fallback path"
    )


def test_update_prefers_flat_docs() -> None:
    text = _text(UPDATE_MD)
    assert _names_flat_docs_preferred(text), (
        "rabbit-spec-update SKILL.md must name the flat docs/ layout as the "
        "preferred/canonical layout and specs/ + docs/spec/ as the "
        "fallback/legacy layouts"
    )


def test_create_mentions_all_layouts() -> None:
    text = _text(CREATE_MD)
    assert "docs/spec.md" in text, (
        "rabbit-spec-create SKILL.md must mention the canonical flat "
        "'docs/spec.md' destination"
    )
    assert "specs/spec.md" in text, (
        "rabbit-spec-create SKILL.md must mention the 'specs/spec.md' "
        "fallback path"
    )
    assert "docs/spec/spec.md" in text, (
        "rabbit-spec-create SKILL.md must mention the legacy "
        "'docs/spec/spec.md' path"
    )


def test_create_canonical_flat_docs() -> None:
    text = _text(CREATE_MD)
    assert _names_flat_docs_preferred(text), (
        "rabbit-spec-create SKILL.md must name the flat docs/ layout as the "
        "canonical destination for new specs and specs/ + docs/spec/ as the "
        "existing-layout fallbacks"
    )


def test_creator_agent_targets_flat_docs() -> None:
    text = _text(CREATOR_AGENT)
    assert "docs/spec.md" in text, (
        "rabbit-spec-creator agent must name the flat 'docs/spec.md' target"
    )
    # The legacy docs/spec/spec.md path must NOT be the agent's sole named
    # target — the flat docs/spec.md is the canonical new location.
    assert "docs/spec/spec.md" not in text, (
        "rabbit-spec-creator agent must not name the legacy "
        "'docs/spec/spec.md' as its target after the flat-docs migration"
    )


def test_rabbit_spec_self_on_specs() -> None:
    assert (FEATURE_DIR / "specs" / "spec.md").exists(), (
        "rabbit-spec must carry specs/spec.md during Phase 2a (no files "
        "move yet)"
    )
    assert (FEATURE_DIR / "specs" / "contract.md").exists(), (
        "rabbit-spec must carry specs/contract.md during Phase 2a"
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
