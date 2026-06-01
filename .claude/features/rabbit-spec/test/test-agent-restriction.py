#!/usr/bin/env python3
"""test-agent-restriction.py — rabbit-spec Inv 2.

Asserts the spec-creator agent file exists with the load-bearing
read-only tool restriction in its YAML frontmatter.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
import os
import re
import sys

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(FEATURE_DIR, "agents/spec-creator.md")

if not os.path.isfile(AGENT):
    print(f"FAIL: agent file not found at {AGENT}", file=sys.stderr)
    sys.exit(1)

with open(AGENT) as f:
    content = f.read()

m = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
if not m:
    print("FAIL: no YAML frontmatter", file=sys.stderr)
    sys.exit(1)

frontmatter = m.group(1)

def field(name):
    m = re.search(rf"^{name}:\s*(.+)$", frontmatter, re.MULTILINE)
    return m.group(1).strip() if m else None

name = field("name")
tools = field("tools")

errors = []
if name != "spec-creator":
    errors.append(f"name must be 'spec-creator', got {name!r}")
if tools != "Read, Grep, Glob":
    errors.append(f"tools must be exactly 'Read, Grep, Glob', got {tools!r}")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: spec-creator agent has correct name and load-bearing tool restriction")
