#!/usr/bin/env python3
"""test-spec-create-skill-retired.py — rabbit-spec Inv 1 (#922).

End-to-end guard for the retirement of the rabbit-spec-create skill wrapper
and the rename of its input assembler. The rabbit-spec-creator subagent now
drafts AND writes its own docs/spec.md; the skill wrapper is gone.

Asserts, against the live on-disk feature:
  - skills/rabbit-spec-create/SKILL.md source is REMOVED.
  - scripts/dispatch-spec-create.py is gone; scripts/dispatch-spec-creator.py
    exists and is executable.
  - feature.json surface.skills does NOT list rabbit-spec-create; surface.scripts
    lists dispatch-spec-creator.py (not the old name); surface.agents still lists
    the agent.
  - feature.json manifest has NO publish_skill entry sourcing the retired skill,
    but DOES retain the publish_agent entry for the subagent.

Static check; no runtime behaviour.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
OLD_SKILL = FEATURE_DIR / "skills" / "rabbit-spec-create" / "SKILL.md"
OLD_SCRIPT = FEATURE_DIR / "scripts" / "dispatch-spec-create.py"
NEW_SCRIPT = FEATURE_DIR / "scripts" / "dispatch-spec-creator.py"
FEATURE_JSON = FEATURE_DIR / "feature.json"

errors: list[str] = []

if OLD_SKILL.exists():
    errors.append(f"retired skill source still present: {OLD_SKILL}")
if (FEATURE_DIR / "skills" / "rabbit-spec-create").is_dir():
    errors.append("retired skills/rabbit-spec-create/ directory still present")

if OLD_SCRIPT.exists():
    errors.append(f"old script name still present: {OLD_SCRIPT}")
if not NEW_SCRIPT.is_file():
    errors.append(f"renamed input assembler missing: {NEW_SCRIPT}")
elif not os.access(NEW_SCRIPT, os.X_OK):
    errors.append(f"renamed input assembler not executable: {NEW_SCRIPT}")

data = json.loads(FEATURE_JSON.read_text())
surface = data.get("surface", {})

skills = surface.get("skills", [])
if any("rabbit-spec-create/" in s for s in skills):
    errors.append(f"surface.skills still lists the retired skill: {skills}")

scripts = surface.get("scripts", [])
if any("dispatch-spec-create.py" in s for s in scripts):
    errors.append(f"surface.scripts still lists the old script name: {scripts}")
if not any("dispatch-spec-creator.py" in s for s in scripts):
    errors.append(f"surface.scripts must list dispatch-spec-creator.py: {scripts}")

agents = surface.get("agents", [])
if not any("rabbit-spec-creator.md" in a for a in agents):
    errors.append(f"surface.agents must still list the subagent: {agents}")

manifest = data.get("manifest", [])
for entry in manifest:
    if entry.get("api") == "publish_skill":
        src = entry.get("args", {}).get("source", "")
        if "rabbit-spec-create/" in src:
            errors.append(
                f"manifest still has a publish_skill for the retired skill: {src}"
            )
has_publish_agent = any(
    e.get("api") == "publish_agent"
    and "rabbit-spec-creator.md" in e.get("args", {}).get("source", "")
    for e in manifest
)
if not has_publish_agent:
    errors.append("manifest must retain publish_agent for rabbit-spec-creator.md")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: rabbit-spec-create skill retired; dispatch-spec-creator.py + "
      "subagent surface intact")
