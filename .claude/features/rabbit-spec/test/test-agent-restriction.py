#!/usr/bin/env python3
"""test-agent-restriction.py — rabbit-spec Inv 2.

Asserts the rabbit-spec-creator agent file exists with the load-bearing
read-only tool restriction in its YAML frontmatter, and (end-to-end) that
the deployed copy under .claude/agents/ uses the rabbit- prefixed base name
required by contract.lib.checks.check_naming (Inv 10/15) — with the old
spec-creator.md removed.

Version: 1.1.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
import os
import re
import sys

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# repo_root = .../<root>; FEATURE_DIR = <root>/.claude/features/rabbit-spec
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(FEATURE_DIR)))
AGENT = os.path.join(FEATURE_DIR, "agents/rabbit-spec-creator.md")
OLD_AGENT = os.path.join(FEATURE_DIR, "agents/spec-creator.md")
DEPLOYED = os.path.join(REPO_ROOT, ".claude/agents/rabbit-spec-creator.md")
OLD_DEPLOYED = os.path.join(REPO_ROOT, ".claude/agents/spec-creator.md")

if not os.path.isfile(AGENT):
    print(f"FAIL: agent file not found at {AGENT}", file=sys.stderr)
    sys.exit(1)
if os.path.exists(OLD_AGENT):
    print(f"FAIL: stale source agent still present at {OLD_AGENT}", file=sys.stderr)
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
if name != "rabbit-spec-creator":
    errors.append(f"name must be 'rabbit-spec-creator', got {name!r}")
if tools != "Read, Grep, Glob":
    errors.append(f"tools must be exactly 'Read, Grep, Glob', got {tools!r}")

# End-to-end: the agent is deployed under the rabbit- prefixed name and the
# stale spec-creator.md deployment is gone.
if not os.path.isfile(DEPLOYED):
    errors.append(f"deployed agent not found at {DEPLOYED}")
if os.path.exists(OLD_DEPLOYED):
    errors.append(f"stale deployed agent still present at {OLD_DEPLOYED}")

# End-to-end: contract.lib.checks.check_naming passes for the repo's agents.
sys.path.insert(0, os.path.join(REPO_ROOT, ".claude", "features"))
try:
    from contract.lib.checks import check_naming
    res = check_naming(REPO_ROOT)
    if not res.passed:
        spec_msgs = [m for m in res.messages if "spec-creator" in m]
        if spec_msgs:
            errors.append("check_naming flags spec-creator: " + "; ".join(spec_msgs))
except Exception as e:
    errors.append(f"could not run check_naming: {e}")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: rabbit-spec-creator agent has correct name, load-bearing tool "
      "restriction, and rabbit- prefixed deployment")
