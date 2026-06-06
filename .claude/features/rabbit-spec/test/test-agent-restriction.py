#!/usr/bin/env python3
"""test-agent-restriction.py — rabbit-spec Inv 2.

Asserts the rabbit-spec-creator agent file exists with the UPGRADED tool
surface (post-#922 it is write-capable, not read-only) and the load-bearing
body mandates, and (end-to-end) that the deployed copy under .claude/agents/
uses the rabbit- prefixed base name required by
contract.lib.checks.check_naming (Inv 10/15) — with the old spec-creator.md
removed.

Post-#922 the rabbit-spec-creator subagent drafts AND writes its own
docs/spec.md. The frontmatter `tools` list MUST grant Write and Explore
alongside Read/Grep/Glob; the body MUST mandate (a) docs/spec.md as the SOLE
write target, (b) Explore-superpower codebase reading, and (c) a contracted
{path_written, summary} handoff that does NOT echo the full spec body.

Version: 2.0.0
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
body = content[m.end():]

def field(name):
    fm = re.search(rf"^{name}:\s*(.+)$", frontmatter, re.MULTILINE)
    return fm.group(1).strip() if fm else None

name = field("name")
tools = field("tools")

errors = []
if name != "rabbit-spec-creator":
    errors.append(f"name must be 'rabbit-spec-creator', got {name!r}")

# The agent is now write-capable: tools MUST include Write and Explore
# alongside the read trio. No longer read-only.
tool_set = {t.strip() for t in (tools or "").split(",") if t.strip()}
for required in ("Read", "Grep", "Glob", "Write", "Explore"):
    if required not in tool_set:
        errors.append(
            f"tools must grant {required!r} (write-capable post-#922); "
            f"got {tools!r}"
        )

# Body mandate (a): docs/spec.md is the SOLE write target.
if "docs/spec.md" not in body:
    errors.append("body must name docs/spec.md as the write target")
if not re.search(r"sole write target|SOLE write target", body, re.IGNORECASE):
    errors.append(
        "body must mandate docs/spec.md as the agent's SOLE write target"
    )

# Body mandate (b): Explore-superpower codebase reading.
if "Explore" not in body:
    errors.append("body must mandate use of the Explore superpower")

# Body mandate (c): contracted {path_written, summary} handoff.
if "path_written" not in body or "summary" not in body:
    errors.append(
        "body must mandate the contracted {path_written, summary} handoff"
    )

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

print("PASS: rabbit-spec-creator agent has correct name, write-capable tool "
      "surface (Write+Explore), sole-docs/spec.md-write mandate, Explore "
      "mandate, {path_written, summary} handoff, and rabbit- prefixed deployment")
