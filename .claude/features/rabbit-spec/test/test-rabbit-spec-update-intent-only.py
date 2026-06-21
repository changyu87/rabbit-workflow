#!/usr/bin/env python3
"""Inv 9: rabbit-spec-update SKILL.md intent-only / no-commit mode.

Source-inspection-only test. Asserts the SKILL.md body documents the
additive intent-only (no-commit / emit-intent) mode that:
  (a) is opt-in via a documented flag in the skill args (default behaviour
      unchanged — backward-compatible),
  (b) EMITS the structured spec-intent / impl-suggestion payload (the same
      schema the default mode produces) on stdout as JSON,
  (c) does NOT edit or write the target docs/spec.md and does NOT commit
      anything (it short-circuits AFTER computing the intent and BEFORE
      applying the Step 4 spec edit),
  (d) leaves the default (edit + write) behaviour as the unchanged default.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-spec-update is absorbed into a native
rabbit CLI command that owns its own intent/apply split.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_MD = (
    Path(__file__).resolve().parents[1]
    / "skills/rabbit-spec-update/SKILL.md"
)


def _text() -> str:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    return SKILL_MD.read_text()


def _section(text: str, heading_re: str) -> str:
    # Match the heading line with MULTILINE only (so '.' in heading_re does
    # NOT span newlines), then capture the body up to the next '## ' heading.
    m = re.search(
        rf"^##\s+{heading_re}[^\n]*\n(.*?)(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    assert m, f"SKILL.md is missing a section matching '## {heading_re}'"
    return m.group(1)


def test_intent_only_flag_documented() -> None:
    """The skill body must document an opt-in intent-only / no-commit flag."""
    text = _text()
    assert "--intent-only" in text, (
        "SKILL.md must document the opt-in '--intent-only' flag for the "
        "no-commit / emit-intent mode"
    )


def test_intent_only_has_its_own_section() -> None:
    """The mode must be documented in a dedicated section, not buried."""
    body = _section(_text(), r"Intent-Only Mode")
    assert body.strip(), "intent-only section must have a body"


def test_intent_only_emits_intent_json_on_stdout() -> None:
    """Intent-only mode must EMIT the intent payload as JSON on stdout."""
    body = _section(_text(), r"Intent-Only Mode")
    lower = body.lower()
    assert "stdout" in lower, (
        "intent-only section must state the intent payload is emitted on stdout"
    )
    assert "json" in lower, (
        "intent-only section must state the emitted payload is JSON"
    )
    # The emitted payload reuses the existing impl-suggestion schema verbatim
    # (do not invent a new shape).
    assert "impl-suggestion" in lower or "schema_version" in lower, (
        "intent-only section must reuse the existing impl-suggestion schema "
        "for the emitted intent payload"
    )


def test_intent_only_skips_spec_edit_and_commit() -> None:
    """Intent-only mode must NOT edit/write docs/spec.md and NOT commit."""
    body = _section(_text(), r"Intent-Only Mode")
    lower = body.lower()
    # Must explicitly state it does not edit/write the spec.
    assert "spec.md" in lower, (
        "intent-only section must reference spec.md (to say it is NOT edited)"
    )
    assert ("does not edit" in lower or "do not edit" in lower
            or "must not edit" in lower or "without editing" in lower
            or "skip step 4" in lower or "skips step 4" in lower
            or "no spec edit" in lower), (
        "intent-only section must state it does NOT edit/write docs/spec.md "
        "(skips the Step 4 edit)"
    )
    assert ("does not commit" in lower or "do not commit" in lower
            or "must not commit" in lower or "no commit" in lower
            or "without committing" in lower or "no-commit" in lower), (
        "intent-only section must state it does NOT commit anything"
    )


def test_intent_only_is_additive_default_unchanged() -> None:
    """The default (edit + write) behaviour must be stated as unchanged."""
    body = _section(_text(), r"Intent-Only Mode")
    lower = body.lower()
    assert ("default" in lower), (
        "intent-only section must contrast against the unchanged default "
        "(edit + write) behaviour — the flag is additive/opt-in"
    )


def test_step4_guards_intent_only() -> None:
    """Step 4 (Update the Spec) must be guarded so intent-only short-circuits
    before applying the edit."""
    body = _section(_text(), r"Step 4.*Update the Spec")
    assert "--intent-only" in body or "intent-only" in body.lower(), (
        "Step 4 must reference the intent-only mode so the edit is skipped "
        "when the flag is set (short-circuit before applying the spec edit)"
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
