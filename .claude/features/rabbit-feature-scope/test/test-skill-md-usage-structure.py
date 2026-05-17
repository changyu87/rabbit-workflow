#!/usr/bin/env python3
# test-skill-md-usage-structure.py
# E2E test for Invariant 9: SKILL.md Usage section MUST present shell-executable
# commands and Claude tool-invocation pseudo-code in SEPARATE fenced code blocks
# with distinct fence labels. The shell command (PROMPT=$(...)) lives in a
# ```bash``` fence; the Agent(...) call lives in a NON-bash fence (e.g. ```text```)
# preceded by prose explicitly stating it is a Claude tool call and must NOT be
# shell-executed.
#
# This protects against RABBIT-FEATURE-SCOPE-BUG-1: agents reading SKILL.md
# literally will shell-exec any line inside a ```bash``` fence — including the
# Agent(...) pseudo-call — which always fails (tcsh: "no matches found"; bash:
# "command not found").

import re
import subprocess
import sys
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
SKILL_PATHS = [
    Path(repo_root) / ".claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md",
    Path(repo_root) / ".claude/skills/rabbit-feature-scope/SKILL.md",
]

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


FENCE_RE = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")


def extract_usage_section(text):
    """Return the slice of text between '## Usage' and the next '## ' heading."""
    lines = text.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "## Usage":
            start = i + 1
        elif start is not None and line.startswith("## "):
            end = i
            break
    if start is None:
        return None
    return lines[start:end]


def extract_fences(section_lines):
    """Return list of (fence_label, body_lines, prose_before_lines) for each fenced block."""
    fences = []
    in_fence = False
    cur_label = None
    cur_body = []
    prose_buffer = []
    prose_before_current = []
    for line in section_lines:
        m = FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence = True
                cur_label = m.group(1)
                cur_body = []
                prose_before_current = list(prose_buffer)
                prose_buffer = []
            else:
                fences.append((cur_label, list(cur_body), list(prose_before_current)))
                in_fence = False
                cur_label = None
                cur_body = []
                prose_before_current = []
        else:
            if in_fence:
                cur_body.append(line)
            else:
                prose_buffer.append(line)
    return fences


def check_skill(skill_path):
    label = str(skill_path.relative_to(repo_root))
    if not skill_path.is_file():
        fail(f"{label}: file missing")
        return
    text = skill_path.read_text()
    section = extract_usage_section(text)
    if section is None:
        fail(f"{label}: no '## Usage' section found")
        return

    fences = extract_fences(section)
    if not fences:
        fail(f"{label}: Usage section has no fenced code blocks")
        return

    # Find the bash fence (with PROMPT=) and the Agent() fence
    bash_fence = None
    agent_fence = None
    for lbl, body, prose in fences:
        body_text = "\n".join(body)
        if lbl == "bash" and "PROMPT=" in body_text:
            bash_fence = (lbl, body, prose, body_text)
        if "Agent(" in body_text:
            agent_fence = (lbl, body, prose, body_text)

    # (a) bash fence contains PROMPT= but does NOT contain Agent(
    if bash_fence is None:
        fail(f"{label}: no ```bash``` fence containing PROMPT= found in Usage")
    else:
        _, _, _, bash_body = bash_fence
        if "Agent(" not in bash_body:
            ok(f"{label}: bash fence does not contain Agent(")
        else:
            fail(f"{label}: bash fence contains Agent( — invariant 9 violated (shell will try to exec it)")

    # (b) Agent( appears only inside a non-bash fence (and is in some fence)
    if agent_fence is None:
        fail(f"{label}: no fence containing Agent( found in Usage section")
    else:
        agent_label, _, agent_prose, _ = agent_fence
        if agent_label != "bash":
            ok(f"{label}: Agent( appears in a non-bash fence (label='{agent_label}')")
        else:
            fail(f"{label}: Agent( appears in a ```bash``` fence — must be non-shell fence")

        # (c) prose immediately preceding the Agent fence must explicitly state
        # it is a Claude tool call and must NOT be shell-executed.
        prose_text = "\n".join(agent_prose).lower()
        mentions_claude_tool = ("claude tool" in prose_text) or ("tool call" in prose_text) or ("tool invocation" in prose_text)
        mentions_not_shell = ("not" in prose_text) and (
            "shell" in prose_text or "shell-exec" in prose_text or "execute" in prose_text or "exec" in prose_text
        )
        if mentions_claude_tool:
            ok(f"{label}: prose before Agent fence mentions Claude tool call")
        else:
            fail(f"{label}: prose before Agent fence missing 'Claude tool call' wording")
        if mentions_not_shell:
            ok(f"{label}: prose before Agent fence warns it is NOT to be shell-executed")
        else:
            fail(f"{label}: prose before Agent fence missing 'NOT shell-executed' warning")

    # (d) Additionally: the two must be in SEPARATE fences (distinct fence indices).
    if bash_fence and agent_fence:
        bash_body_text = bash_fence[3]
        agent_body_text = agent_fence[3]
        if bash_body_text != agent_body_text:
            ok(f"{label}: shell command and Agent() call are in separate fences")
        else:
            fail(f"{label}: shell command and Agent() call share the same fence body")


for p in SKILL_PATHS:
    check_skill(p)

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
