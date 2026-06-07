#!/usr/bin/env python3
"""Inv 57 — the rabbit-tdd-subagent agent definition enables the Skill tool.

Parses the YAML frontmatter `tools:` list of BOTH the source
agents/rabbit-tdd-subagent.md AND the deployed
.claude/agents/rabbit-tdd-subagent.md and asserts each list contains
`Skill` plus all six original tools (Read, Write, Edit, Bash, Glob, Grep).
Without `Skill` the subagent cannot honor Inv 11's SKILL.md-routing rule
(Skill("skill-creator:skill-creator")) or Inv 17's CODE-REVIEW step
(Skill("superpowers:requesting-code-review")).
"""
import os

from _helpers import AGENT_PATH, REPO_ROOT, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


DEPLOYED_PATH = os.path.join(
    REPO_ROOT, ".claude", "agents", "rabbit-tdd-subagent.md"
)

REQUIRED_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"]


def parse_tools(path):
    """Extract the `tools:` frontmatter list as a set of tool names."""
    with open(path) as f:
        lines = f.read().splitlines()
    # Frontmatter is delimited by the first two '---' lines.
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("tools:"):
            raw = line[len("tools:"):].strip()
            return {t.strip() for t in raw.split(",") if t.strip()}
    return None


for label, path in (("source", AGENT_PATH), ("deployed", DEPLOYED_PATH)):
    if not os.path.isfile(path):
        ko(f"inv57: {label} agent file missing at {path}")
        continue
    tools = parse_tools(path)
    if tools is None:
        ko(f"inv57: {label} agent file has no parseable tools: frontmatter")
        continue
    missing = [t for t in REQUIRED_TOOLS if t not in tools]
    if missing:
        ko(f"inv57: {label} tools: missing {missing} (got {sorted(tools)})")
    else:
        ok(f"inv57: {label} tools: includes Skill plus the six original tools")

report(passed, failed)
