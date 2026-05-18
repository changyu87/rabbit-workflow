#!/usr/bin/env python3
"""check-opus-for-planning-agents.py — enforce: any subagent whose description
implies brainstorming, spec-writing, planning, design, or architecture work
MUST declare model: opus in its frontmatter.

Scans $AGENTS_DIR (default: .claude/agents/), reads YAML frontmatter, and
emits a violation per non-conformant agent.

Exit: 0 all conformant (or no agents); 1 one or more violations.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when agent model enforcement is provided by a native linter.
"""

import os
import re
import sys


PATTERN = re.compile(r'brainstorm|spec|plan|design|architect', re.IGNORECASE)


def parse_frontmatter(filepath):
    """Return dict of key: value from YAML frontmatter (between --- lines)."""
    data = {}
    with open(filepath) as f:
        lines = f.readlines()

    in_front = False
    count = 0
    for line in lines:
        stripped = line.rstrip('\n')
        if stripped == '---':
            count += 1
            if count == 1:
                in_front = True
                continue
            elif count == 2:
                break
        if in_front:
            if ':' in stripped:
                key, _, val = stripped.partition(':')
                data[key.strip()] = val.strip()
    return data


def main():
    agents_dir = os.environ.get("AGENTS_DIR", ".claude/agents")

    if not os.path.isdir(agents_dir):
        print(f"OK: no agents dir at {agents_dir} (vacuous pass)")
        sys.exit(0)

    violations = 0
    md_files = [
        f for f in os.listdir(agents_dir) if f.endswith(".md")
    ]

    for fname in sorted(md_files):
        fpath = os.path.join(agents_dir, fname)
        front = parse_frontmatter(fpath)
        name = front.get("name", "")
        desc = front.get("description", "")
        model = front.get("model", "")

        if PATTERN.search(desc):
            if model != "opus":
                print(
                    f"VIOLATION: agent '{name}' (file: {fpath}) — "
                    f"description triggers planning rule but model='{model or '<unset>'}' (must be 'opus').",
                    file=sys.stderr
                )
                violations += 1

    if violations > 0:
        print(f"FAIL: {violations} agent(s) violate Opus-for-planning rule.", file=sys.stderr)
        sys.exit(1)

    print("OK: all planning-class agents declare model: opus")
    sys.exit(0)


if __name__ == "__main__":
    main()
