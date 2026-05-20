#!/usr/bin/env python3
"""E2E test coverage for rabbit-feature Inv 5-8.

Locks four behaviours of `rabbit-feature-touch` SKILL.md that previously
had no direct test:

- Inv 5 — normal-mode Step 1 resolves scope via the `rabbit-feature-scope`
  Skill tool, NOT by shelling out to `resolve-scope.py`.
- Inv 6 — the unified sequence is exactly seven numbered steps with the
  documented names (Scope Resolution, Create Branch, Spec Authoring,
  Human Approval, Dispatch TDD Subagents, Collect and Verify HANDOFFs,
  PR / Hand Off).
- Inv 7 — Step 4 (Human Approval) is a dispatcher-side gate that lives
  in the main session, not inside the TDD subagent.
- Inv 8 — when the `.rabbit-human-approval-bypass` marker is present,
  Step 4 documents passing `--human-approval-gate false` to the Step 5
  `dispatch-tdd-subagent.py` invocation.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: When feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_MD = (
    REPO_ROOT
    / ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"
)

# Expected seven-step heading names, in order.
EXPECTED_STEPS = [
    (1, "Scope Resolution"),
    (2, "Create Branch"),
    (3, "Spec Authoring"),
    (4, "Human Approval"),
    (5, "Dispatch TDD Subagents"),
    (6, "Collect and Verify HANDOFFs"),
    (7, "PR / Hand Off"),
]

# Heading regex: matches '### Step N — Title' with either em-dash or hyphen.
STEP_HEADING_RE = re.compile(
    r"^###\s+Step\s+(\d+)\s+[-—]\s+(.+?)\s*$",
    re.MULTILINE,
)


def _read_skill_md() -> str:
    assert SKILL_MD.exists(), f"missing SKILL.md: {SKILL_MD}"
    return SKILL_MD.read_text()


def _extract_step_body(text: str, step_num: int) -> str:
    """Return the body of a numbered step section (up to the next ### or ## heading)."""
    pattern = (
        rf"^###\s+Step\s+{step_num}\s+[-—]\s+.+?\s*$(.*?)(?=^###\s|^##\s|\Z)"
    )
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    assert m, f"SKILL.md is missing a 'Step {step_num}' section"
    return m.group(1)


# ---------------------------------------------------------------------------
# Inv 5 — Step 1 normal mode uses Skill tool, not python3 resolve-scope.py
# ---------------------------------------------------------------------------


def test_inv5_step1_normal_mode_uses_skill_tool() -> None:
    body = _extract_step_body(_read_skill_md(), 1)
    # Look at the Normal-mode block specifically.
    normal_match = re.search(
        r"\*\*Normal mode:\*\*(.*?)(?=\*\*B/B mode:\*\*|\Z)",
        body,
        re.DOTALL,
    )
    assert normal_match, "Step 1 must contain a '**Normal mode:**' block"
    normal_body = normal_match.group(1)

    # Must invoke the Skill tool with rabbit-feature-scope.
    assert 'Skill("rabbit-feature-scope"' in normal_body, (
        'Step 1 normal mode must invoke Skill("rabbit-feature-scope", ...); '
        "shell-out to resolve-scope.py is no longer permitted"
    )


def test_inv5_step1_normal_mode_does_not_shell_out_resolve_scope() -> None:
    body = _extract_step_body(_read_skill_md(), 1)
    normal_match = re.search(
        r"\*\*Normal mode:\*\*(.*?)(?=\*\*B/B mode:\*\*|\Z)",
        body,
        re.DOTALL,
    )
    assert normal_match, "Step 1 must contain a '**Normal mode:**' block"
    normal_body = normal_match.group(1)

    # The normal-mode block must NOT instruct a direct shell-out to
    # resolve-scope.py (that is a legacy pattern superseded by the
    # Skill-tool invocation).
    shellout = re.search(
        r"python3\s+[^\n]*resolve-scope\.py",
        normal_body,
    )
    assert shellout is None, (
        "Step 1 normal mode must NOT shell out to resolve-scope.py; "
        "use Skill(\"rabbit-feature-scope\", ...) instead"
    )


# ---------------------------------------------------------------------------
# Inv 6 — seven numbered step headings, in order, with documented names
# ---------------------------------------------------------------------------


def test_inv6_exactly_seven_steps() -> None:
    text = _read_skill_md()
    headings = STEP_HEADING_RE.findall(text)
    assert len(headings) == 7, (
        f"SKILL.md must declare exactly 7 numbered step headings; "
        f"found {len(headings)}: {headings}"
    )


def test_inv6_step_numbers_in_order() -> None:
    text = _read_skill_md()
    nums = [int(n) for n, _ in STEP_HEADING_RE.findall(text)]
    assert nums == [1, 2, 3, 4, 5, 6, 7], (
        f"Step headings must be numbered 1..7 in order; got {nums}"
    )


def test_inv6_step_names_match_spec() -> None:
    text = _read_skill_md()
    found = STEP_HEADING_RE.findall(text)
    for (expected_num, expected_name), (got_num, got_name) in zip(
        EXPECTED_STEPS, found
    ):
        assert int(got_num) == expected_num, (
            f"Step ordering mismatch: expected {expected_num}, got {got_num}"
        )
        assert got_name.strip() == expected_name, (
            f"Step {expected_num} must be named "
            f"'{expected_name}', got '{got_name.strip()}'"
        )


def test_inv6_overview_describes_seven_steps() -> None:
    text = _read_skill_md()
    # The unified-sequence overview heading must reflect "Seven".
    assert re.search(
        r"##\s+Unified\s+Seven-Step\s+Sequence",
        text,
    ), (
        "SKILL.md must declare the unified sequence as 'Seven-Step' "
        "in the section heading"
    )


# ---------------------------------------------------------------------------
# Inv 7 — Step 4 is a dispatcher-side gate in the main session
# ---------------------------------------------------------------------------


def test_inv7_step4_lives_in_main_session() -> None:
    body = _extract_step_body(_read_skill_md(), 4)
    # The narrative must state the gate lives in the main session
    # (i.e., dispatcher-side, not inside the subagent).
    assert "lives here, in the main session" in body, (
        "Step 4 must explicitly state the gate 'lives here, in the main "
        "session' to lock its dispatcher-side semantics (Inv 7)"
    )


def test_inv7_step4_explains_subagent_cannot_pause() -> None:
    body = _extract_step_body(_read_skill_md(), 4).lower()
    # The rationale (why the gate cannot live inside the subagent)
    # must be present: subagents run to completion / cannot pause for
    # user input.
    assert "subagents run to completion" in body or (
        "cannot pause" in body and "user input" in body
    ), (
        "Step 4 must explain why the gate cannot live in the subagent "
        "(e.g., 'subagents run to completion and cannot pause for user input')"
    )


# ---------------------------------------------------------------------------
# Inv 8 — marker-present path documents passing --human-approval-gate false
# ---------------------------------------------------------------------------


def test_inv8_step4_marker_present_passes_gate_false() -> None:
    body = _extract_step_body(_read_skill_md(), 4)
    # The marker-present branch must document passing
    # --human-approval-gate false to dispatch-tdd-subagent.py at Step 5.
    assert "--human-approval-gate false" in body, (
        "Step 4 must document passing '--human-approval-gate false' "
        "to the Step 5 dispatch when the bypass marker is present (Inv 8)"
    )
    assert "dispatch-tdd-subagent.py" in body, (
        "Step 4 must reference 'dispatch-tdd-subagent.py' as the Step 5 "
        "invocation that receives the --human-approval-gate flag (Inv 8)"
    )


def test_inv8_step4_marker_absent_default_gate_true() -> None:
    body = _extract_step_body(_read_skill_md(), 4)
    # The marker-absent branch must document the default (gate active):
    # either by explicitly passing 'true' or by stating the flag is omitted
    # because true is the default.
    assert "--human-approval-gate true" in body, (
        "Step 4 must document the marker-absent default path passing "
        "'--human-approval-gate true' (or noting true is the default)"
    )


def main() -> int:
    tests = [
        test_inv5_step1_normal_mode_uses_skill_tool,
        test_inv5_step1_normal_mode_does_not_shell_out_resolve_scope,
        test_inv6_exactly_seven_steps,
        test_inv6_step_numbers_in_order,
        test_inv6_step_names_match_spec,
        test_inv6_overview_describes_seven_steps,
        test_inv7_step4_lives_in_main_session,
        test_inv7_step4_explains_subagent_cannot_pause,
        test_inv8_step4_marker_present_passes_gate_false,
        test_inv8_step4_marker_absent_default_gate_true,
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
