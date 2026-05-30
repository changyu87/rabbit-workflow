#!/usr/bin/env python3
"""Inv 4-9, 12, 14-16, 41: rabbit-feature-touch SKILL.md content.

Locks the rabbit-feature-touch SKILL.md (and the deployed copy) against
drift on the seven-step sequence, scope-resolution invocation, spec
authoring invocation, Step 3 spec-commit obligation, Step 4 human-approval
semantics (dispatcher-side gate, bypass marker mechanism, alert routing
via emit_configurable_alert), and Red Flags content. Inv 10 and Inv 11
retired in the TDD-SUBAGENT-BACKLOG-19 cascade (the --human-approval-gate
CLI flag was removed in tdd-subagent v5.0.0); Inv 13 and Inv 42 retired in
the Phase 7c cleanup (B/B mode removed from the SKILL.md after rabbit-file
retirement in Phase 7b). A regression guard asserts the
--human-approval-gate flag string is absent from both source and deployed
SKILL.md.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_SKILL = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"
)
DEPLOYED_SKILL = REPO_ROOT / ".claude/skills/rabbit-feature-touch/SKILL.md"

EXPECTED_STEPS = [
    (1, "Scope Resolution"),
    (2, "Create Branch"),
    (3, "Spec Authoring"),
    (4, "Human Approval"),
    (5, "Dispatch TDD Subagents"),
    (6, "Collect and Verify HANDOFFs"),
    (7, "PR / Hand Off"),
]
STEP_HEADING_RE = re.compile(
    r"^###\s+Step\s+(\d+)\s+[-—]\s+(.+?)\s*$", re.MULTILINE
)
MARKER_PATH = ".rabbit-human-approval-bypass"
REVOKE_CMD = "/rabbit-config human-approval true"
ALERT_TEXT = "HUMAN APPROVAL BYPASS ACTIVE"


def _text() -> str:
    assert SOURCE_SKILL.exists(), f"missing SKILL.md: {SOURCE_SKILL}"
    return SOURCE_SKILL.read_text(encoding="utf-8")


def _step_body(text: str, n: int) -> str:
    m = re.search(
        rf"^###\s+Step\s+{n}\s+[-—]\s+.+?\s*$(.*?)(?=^###\s|^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, f"SKILL.md is missing a 'Step {n}' section"
    return m.group(1)


def _red_flags(text: str) -> str:
    m = re.search(
        r"^##\s+Red Flags[^\n]*$(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "SKILL.md is missing a '## Red Flags' section"
    return m.group(1)


# Inv 4: seven-step sequence
def test_inv4_overview_heading_says_seven_step() -> None:
    assert re.search(r"##\s+Seven-Step\s+Sequence", _text()), (
        "SKILL.md must declare the sequence as 'Seven-Step' in the section heading"
    )


def test_inv4_seven_step_headings_in_order() -> None:
    headings = STEP_HEADING_RE.findall(_text())
    assert len(headings) == 7, (
        f"SKILL.md must declare exactly 7 numbered step headings; found {len(headings)}: {headings}"
    )
    for (exp_n, exp_name), (got_n, got_name) in zip(EXPECTED_STEPS, headings):
        assert int(got_n) == exp_n, f"step ordering mismatch: expected {exp_n}, got {got_n}"
        assert got_name.strip() == exp_name, (
            f"Step {exp_n} must be named {exp_name!r}, got {got_name.strip()!r}"
        )


# Inv 5: Step 1 uses Skill("rabbit-feature-scope")
def test_inv5_step_1_uses_scope_skill() -> None:
    body = _step_body(_text(), 1)
    assert 'Skill("rabbit-feature-scope"' in body, (
        'Step 1 must invoke Skill("rabbit-feature-scope", ...); '
        "shell-out to resolve-scope.py is not permitted"
    )


# Inv 6: Step 3 invokes Skill("rabbit-feature-spec")
def test_inv6_step_3_uses_spec_skill() -> None:
    body = _step_body(_text(), 3)
    assert 'Skill("rabbit-feature-spec"' in body, (
        'Step 3 must invoke Skill("rabbit-feature-spec", ...)'
    )


# Inv 7: Step 4 lives in the main session
def test_inv7_step_4_lives_in_main_session() -> None:
    body = _step_body(_text(), 4)
    assert "lives here, in the main session" in body, (
        "Step 4 must state the gate 'lives here, in the main session'"
    )
    lower = body.lower()
    assert "subagents run to completion" in lower or (
        "cannot pause" in lower and "user input" in lower
    ), (
        "Step 4 must explain why the gate cannot live in the subagent "
        "(e.g., 'subagents run to completion and cannot pause for user input')"
    )


# Inv 8: Step 4 bypass mechanism named
def test_inv8_step_4_names_marker_and_command() -> None:
    body = _step_body(_text(), 4)
    assert MARKER_PATH in body, f"Step 4 must name the marker path {MARKER_PATH!r}"
    assert REVOKE_CMD in body, f"Step 4 must name the revoke command {REVOKE_CMD!r}"


# Inv 9: bypass-check is the FIRST action of Step 4
def test_inv9_bypass_check_is_first_action() -> None:
    body = _step_body(_text(), 4)
    marker_pos = body.find(MARKER_PATH)
    assert marker_pos != -1, f"Step 4 must reference {MARKER_PATH!r}"
    for label, needle in [("impl-suggestion", "impl-suggestion"), ("wait", "wait for explicit")]:
        pos = body.lower().find(needle)
        if pos != -1:
            assert marker_pos < pos, (
                f"bypass marker check must precede {label} mention "
                f"(marker at {marker_pos}, {label} at {pos})"
            )


# Inv 10 + Inv 11 retired (TDD-SUBAGENT-BACKLOG-19 cascade) — the
# --human-approval-gate CLI flag was removed in tdd-subagent v5.0.0, so
# the assertions that the SKILL.md documents passing that flag no longer
# apply. Regression guard: the flag string MUST NOT appear anywhere in
# either the source or deployed SKILL.md.
def test_no_human_approval_gate_flag_in_source_skill() -> None:
    text = _text()
    assert "--human-approval-gate" not in text, (
        "source SKILL.md must NOT reference the retired '--human-approval-gate' "
        "flag (TDD-SUBAGENT-BACKLOG-19 cascade)"
    )


def test_no_human_approval_gate_flag_in_deployed_skill() -> None:
    assert DEPLOYED_SKILL.exists(), f"missing deployed SKILL.md: {DEPLOYED_SKILL}"
    text = DEPLOYED_SKILL.read_text(encoding="utf-8")
    assert "--human-approval-gate" not in text, (
        "deployed SKILL.md must NOT reference the retired '--human-approval-gate' "
        "flag (TDD-SUBAGENT-BACKLOG-19 cascade)"
    )


# Inv 12: Step 4 bypass-active path routes the alert through
# contract.lib.runtime.emit_configurable_alert(rabbit-cage, human-approval).
# The SKILL.md must reference the helper and the configurable coordinates;
# it must NOT inline the alert-message text (single source of truth is the
# rabbit-cage human-approval configurable's alert-message field).
def _assert_inv12(text: str, label: str) -> None:
    body = _step_body(text, 4)
    assert "emit_configurable_alert" in body, (
        f"Step 4 ({label}) must invoke emit_configurable_alert"
    )
    assert "rabbit-cage" in body, (
        f"Step 4 ({label}) must reference the 'rabbit-cage' feature when "
        "invoking emit_configurable_alert"
    )
    assert "human-approval" in body, (
        f"Step 4 ({label}) must reference the 'human-approval' configurable "
        "when invoking emit_configurable_alert"
    )
    assert ALERT_TEXT not in body, (
        f"Step 4 ({label}) must NOT inline the alert-message text {ALERT_TEXT!r}; "
        "the centrally-declared alert text lives in rabbit-cage/feature.json"
    )


def test_inv12_source_step4_uses_emit_configurable_alert() -> None:
    _assert_inv12(_text(), "source SKILL.md")


def test_inv12_deployed_step4_uses_emit_configurable_alert() -> None:
    assert DEPLOYED_SKILL.exists(), f"missing deployed SKILL.md: {DEPLOYED_SKILL}"
    _assert_inv12(DEPLOYED_SKILL.read_text(encoding="utf-8"), "deployed SKILL.md")


# Inv 13 retired in Phase 7c cleanup — B/B mode (and the item.json read
# path the assertion locked) was removed from the SKILL.md after rabbit-file
# retirement in Phase 7b.


# Inv 14: Red Flags — no main-session Write/Edit on features
def test_inv14_red_flags_prohibit_write_edit_on_features() -> None:
    body = _red_flags(_text())
    lower = body.lower()
    assert "main session" in lower, "Red Flags must mention 'main session' Write/Edit prohibition"
    assert "write" in lower and "edit" in lower, (
        "Red Flags must name both Write and Edit tools"
    )
    assert ".claude/features/" in body, "Red Flags must reference '.claude/features/' path"


# Inv 15: Red Flags — no main-session scope-marker creation
def test_inv15_red_flags_prohibit_scope_marker_creation() -> None:
    body = _red_flags(_text())
    lower = body.lower()
    assert ".rabbit-scope-active" in body, (
        "Red Flags must reference '.rabbit-scope-active' marker name"
    )
    assert ".rabbit-scope-active-" in body, (
        "Red Flags must reference '.rabbit-scope-active-<feature>' per-feature pattern"
    )
    assert "main session" in lower, (
        "Red Flags must mention 'main session' marker-creation prohibition"
    )


# Inv 16: Step 3 spec-commit obligation documented in SKILL.md
def test_inv16_step_3_spec_commit_obligation() -> None:
    for skill_path in (SOURCE_SKILL, DEPLOYED_SKILL):
        assert skill_path.exists(), f"missing SKILL.md: {skill_path}"
        text = skill_path.read_text(encoding="utf-8")
        body = _step_body(text, 3)
        assert "Commit spec changes BEFORE Step 5" in body, (
            f"Step 3 in {skill_path} must contain the literal phrase "
            "'Commit spec changes BEFORE Step 5'"
        )
        assert "spec(<feature-name>): update spec for" in body, (
            f"Step 3 in {skill_path} must document the commit message pattern "
            "'spec(<feature-name>): update spec for ...'"
        )
        assert "git diff --cached --quiet" in body, (
            f"Step 3 in {skill_path} must phrase the empty-diff skip condition "
            "as a 'git diff --cached --quiet' test"
        )


# Inv 41: dispatcher-continuity directive present in source AND deployed,
# byte-identical, prominent enough to appear before Step 7's body ends.
_CONTINUITY_REQUIRED_PHRASES = [
    "MUST NOT end",
    "Step 7",
    "phase boundary",
    "not a turn boundary",
]


def _continuity_block_span(text: str) -> tuple[int, int]:
    """Locate a contiguous span (<= 2000 chars) containing every required phrase.

    Returns (start, end) indices. Raises AssertionError if no such span exists.
    """
    # Find the earliest occurrence of "MUST NOT end" as the anchor.
    anchor = text.find("MUST NOT end")
    assert anchor != -1, (
        "SKILL.md must contain the literal phrase 'MUST NOT end' "
        "(part of the dispatcher-continuity directive)"
    )
    # Expand a window around the anchor and require all phrases inside.
    window_start = max(0, anchor - 500)
    window_end = min(len(text), anchor + 1500)
    window = text[window_start:window_end]
    for phrase in _CONTINUITY_REQUIRED_PHRASES:
        assert phrase in window, (
            f"dispatcher-continuity directive must contain the phrase "
            f"{phrase!r} within ~2000 chars of 'MUST NOT end'"
        )
    return window_start, window_end


def test_inv41_source_has_continuity_directive() -> None:
    text = _text()
    _continuity_block_span(text)


def test_inv41_deployed_has_continuity_directive() -> None:
    assert DEPLOYED_SKILL.exists(), f"missing deployed SKILL.md: {DEPLOYED_SKILL}"
    text = DEPLOYED_SKILL.read_text(encoding="utf-8")
    _continuity_block_span(text)


def test_inv41_source_and_deployed_byte_identical() -> None:
    """Inv 41 requires byte-identical presence of the directive in both files.

    Easiest enforcement: the two SKILL.md files are byte-identical overall
    (which is already the publish contract for this skill).
    """
    assert SOURCE_SKILL.exists(), f"missing source SKILL.md: {SOURCE_SKILL}"
    assert DEPLOYED_SKILL.exists(), f"missing deployed SKILL.md: {DEPLOYED_SKILL}"
    src = SOURCE_SKILL.read_bytes()
    dep = DEPLOYED_SKILL.read_bytes()
    assert src == dep, (
        "source and deployed rabbit-feature-touch SKILL.md must be "
        "byte-identical (Inv 41 requires the continuity directive to "
        "appear byte-identically in both)"
    )


# Inv 42 retired in Phase 7c cleanup — the "B/B item materialization"
# subsection of Step 1 was removed along with the rest of B/B mode after
# rabbit-file retirement in Phase 7b.


def test_inv41_directive_visible_before_step_7_end() -> None:
    """Directive must be prominent enough that a fresh reader sees it
    before reaching the END of Step 7's body. Allowed placements per the
    spec: near the Overview, or as the closing paragraph after Step 7's
    body. Both satisfy "before reaching Step 7" in the sense of "visible
    before/within Step 7 closes"."""
    text = _text()
    anchor = text.find("MUST NOT end")
    assert anchor != -1, "missing 'MUST NOT end' anchor"
    # Find where Step 7's body ends: the next top-level "## " heading after
    # the Step 7 heading, or EOF.
    m = re.search(r"^###\s+Step\s+7\s+[-—]", text, re.MULTILINE)
    assert m, "SKILL.md missing Step 7 heading"
    step7_start = m.start()
    # Locate next "## " (top-level) heading after step7_start
    next_top = re.search(r"^##\s", text[step7_start + 1:], re.MULTILINE)
    if next_top:
        step7_end = step7_start + 1 + next_top.start()
    else:
        step7_end = len(text)
    assert anchor < step7_end, (
        f"dispatcher-continuity directive (at offset {anchor}) must appear "
        f"before the end of Step 7's body (at offset {step7_end})"
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
