#!/usr/bin/env python3
"""Inv 23: rabbit-feature-scope SKILL.md fence separation.

The Usage section presents the shell command and the Agent tool invocation
in separate fenced code blocks with distinct fence labels, with the Agent
block preceded by a sentence stating it is a Claude tool call and MUST NOT
be shell-executed.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when scope resolution is automated by the dispatch
infrastructure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_MD = Path(__file__).resolve().parents[1] / "skills/rabbit-feature-scope/SKILL.md"


def _usage_section(text: str) -> str:
    m = re.search(
        r"^##\s+Usage\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert m, "SKILL.md is missing a '## Usage' section"
    return m.group(1)


def test_fence_separation() -> None:
    body = _usage_section(SKILL_MD.read_text())
    fences = re.findall(r"^```(\w*)\s*$", body, re.MULTILINE)
    assert "bash" in fences, "Usage section must contain a ```bash``` fence for the shell command"
    non_shell = [f for f in fences if f and f != "bash"]
    assert non_shell, (
        f"Usage section must present the Agent tool invocation in a non-bash fence "
        f"(distinct label); fences found: {fences}"
    )


def test_agent_block_warned_against_shell_execution() -> None:
    body = _usage_section(SKILL_MD.read_text())
    lower = body.lower()
    # Look for explicit "Claude tool" and "do NOT shell" guidance prefacing the Agent block.
    assert "claude tool call" in lower, (
        "Usage section must explicitly state the Agent block is a Claude tool call"
    )
    assert "shell-execute" in lower or "shell execute" in lower, (
        "Usage section must explicitly warn against shell-executing the Agent block"
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
