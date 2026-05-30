#!/usr/bin/env python3
"""Inv 26-31: rabbit-feature-spec SKILL.md content.

Covers frontmatter model, request classification, impl-suggestion output
(including generated_at format), spec-update ordering, read-before-edit
contract, and process-agnostic phrasing.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when spec authoring is natively handled by the
rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_MD = Path(__file__).resolve().parents[1] / "skills/rabbit-feature-spec/SKILL.md"

GENERATED_AT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _text() -> str:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    return m.group(1)


def _section(text: str, heading_re: str) -> str:
    m = re.search(
        rf"^##\s+{heading_re}\s*$(.*?)(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    assert m, f"SKILL.md is missing a section matching '## {heading_re}'"
    return m.group(1)


# Inv 26: frontmatter declares model: opus
def test_inv26_model_opus_in_frontmatter() -> None:
    fm = _frontmatter(_text())
    m = re.search(r"^model\s*:\s*(\S+)", fm, re.MULTILINE)
    assert m, "SKILL.md frontmatter must declare 'model:'"
    assert m.group(1) == "opus", (
        f"SKILL.md frontmatter must declare model: opus; got model: {m.group(1)!r}"
    )


# Inv 27: request classification gates superpowers invocation
def test_inv27_classifies_request_before_superpowers() -> None:
    text = _text()
    lower = text.lower()
    assert "open-ended" in lower and "specific" in lower, (
        "SKILL.md must document the open-ended vs specific classification"
    )
    assert "superpowers:brainstorming" in text, (
        "SKILL.md must invoke 'superpowers:brainstorming' for open-ended requests"
    )
    assert "superpowers:writing-plans" in text, (
        "SKILL.md must invoke 'superpowers:writing-plans'"
    )


# Inv 28: impl-suggestion output shape (path + schema_version + generated_at format)
def test_inv28_impl_suggestion_path_and_schema() -> None:
    text = _text()
    assert ".rabbit/impl-suggestion-" in text, (
        "SKILL.md must document writing '.rabbit/impl-suggestion-<feature-name>.json'"
    )
    assert "schema_version" in text and "1.0.0" in text, (
        "SKILL.md must document schema_version 1.0.0"
    )


def test_inv28_generated_at_format() -> None:
    text = _text()
    # The documented format must be the strict YYYY-MM-DDTHH:MM:SSZ form.
    assert "YYYY-MM-DDTHH:MM:SSZ" in text, (
        "SKILL.md must document generated_at format as YYYY-MM-DDTHH:MM:SSZ"
    )
    # Spot-check the example timestamp matches the strict form.
    examples = GENERATED_AT_RE.findall(text)
    assert examples, "SKILL.md must include at least one example timestamp"
    # And no example timestamp with fractional seconds or +00:00 form.
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", text), (
        "SKILL.md must not document fractional-seconds timestamps"
    )
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}", text), (
        "SKILL.md must not document timezone-offset timestamps"
    )


# Inv 29: spec update precedes impl-suggestion write
def test_inv29_spec_update_before_impl_suggestion() -> None:
    text = _text()
    # The numbered steps in the SKILL.md must place spec update (Step 4)
    # before impl-suggestion write (Step 5).
    step_update_m = re.search(
        r"^##\s+Step 4\s+[-—]\s+Update the Spec", text, re.MULTILINE
    )
    step_write_m = re.search(
        r"^##\s+Step 5\s+[-—]\s+Write impl-suggestion", text, re.MULTILINE
    )
    assert step_update_m and step_write_m, (
        "SKILL.md must declare 'Step 4 — Update the Spec' before "
        "'Step 5 — Write impl-suggestion ...'"
    )
    assert step_update_m.start() < step_write_m.start(), (
        "Step 4 (Update the Spec) must appear before Step 5 (Write impl-suggestion)"
    )


# Inv 30: read-before-edit contract
def test_inv30_step_1_must_read_mandate() -> None:
    body = _section(_text(), r"Step 1.*Read Current State")
    assert "MUST Read" in body, (
        "Step 1 must contain the hard 'MUST Read' mandate (capital R)"
    )
    assert "spec.md" in body, "Step 1 mandate must reference 'spec.md'"


def test_inv30_step_4_pre_condition_repeats_obligation() -> None:
    body = _section(_text(), r"Step 4.*Update the Spec")
    assert "PRE-CONDITION" in body, (
        "Step 4 must contain a 'PRE-CONDITION' note repeating the Read obligation"
    )
    # The pre-condition must reference the Read obligation in nearby text.
    pre_pos = body.find("PRE-CONDITION")
    tail = body[pre_pos:pre_pos + 600]
    assert "Read" in tail, (
        "Step 4 PRE-CONDITION must reference the Read obligation"
    )
    # The fallback path ("if you arrive without having Read, Read it now")
    # MUST be documented so a caller arriving at Step 4 without Step 1
    # knows what to do.
    assert "without having Read" in body or "without having read" in body, (
        "Step 4 must document the caller-bypass case (arriving without "
        "having Read the spec.md)"
    )
    assert "Read it now" in body or "read it now" in body, (
        "Step 4 caller-bypass clause must direct the caller to Read the "
        "spec.md now"
    )


# Inv 31: process-agnostic SKILL.md
def test_inv31_no_caller_identification() -> None:
    text = _text()
    # The SKILL.md must NOT identify a specific caller as the primary
    # invocation context.
    forbidden_phrases = [
        "you are invoked as Step 3 in rabbit-feature-touch",
        "Step 3 of rabbit-feature-touch",
        "the TDD subagent reads this file",
    ]
    leaked = [p for p in forbidden_phrases if p in text]
    assert not leaked, (
        f"SKILL.md must be process-agnostic; leaked caller-identification phrases: {leaked}"
    )


def test_inv31_what_you_do_not_do_no_named_skills() -> None:
    text = _text()
    m = re.search(
        r"^##\s+What You Do NOT Do\s*$(.*?)(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    assert m, "SKILL.md must contain a 'What You Do NOT Do' section"
    body = m.group(1)
    # The section must NOT name specific skills to avoid invoking.
    # Generic rules ("do not invoke other skills") are fine.
    forbidden = ["rabbit-feature-touch", "rabbit-feature-new", "rabbit-feature-audit", "rabbit-file"]
    leaked = [name for name in forbidden if name in body]
    assert not leaked, (
        f"'What You Do NOT Do' must not name specific skills or processes; leaked: {leaked}"
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
