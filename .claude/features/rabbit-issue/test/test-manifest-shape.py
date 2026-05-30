#!/usr/bin/env python3
"""feature.json manifest + surface shape for rabbit-issue.

Pins the Phase 1 metadata invariants for rabbit-issue:

  - top-level keys: name, version, owner, summary, deprecation_criterion,
    surface, manifest
  - name == "rabbit-issue"
  - deprecation_criterion is non-empty and non-placeholder (no "TBD")
  - surface.skills contains "rabbit-issue"
  - surface.scripts lists all four runtime scripts:
      scripts/file-item.py, scripts/item-status.py,
      scripts/list-items.py, scripts/_gh.py
  - manifest declares the publish_skill API for skills/rabbit-issue/SKILL.md

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when feature lifecycle management is natively
    handled by Claude Code's workflow mechanism.
"""
import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"

EXPECTED_SCRIPTS = (
    "scripts/file-item.py",
    "scripts/item-status.py",
    "scripts/list-items.py",
    "scripts/_gh.py",
)

REQUIRED_TOP = (
    "name", "version", "owner", "summary",
    "deprecation_criterion", "surface", "manifest",
)


def main() -> int:
    data = json.loads(FEATURE_JSON.read_text())
    fails = []

    for key in REQUIRED_TOP:
        if key not in data:
            fails.append(f"feature.json missing top-level '{key}'")

    if data.get("name") != "rabbit-issue":
        fails.append(f"name must be 'rabbit-issue', got {data.get('name')!r}")

    dep = data.get("deprecation_criterion", "")
    if not dep or "TBD" in dep:
        fails.append(
            f"deprecation_criterion must be set (non-placeholder), got {dep!r}"
        )

    surface = data.get("surface", {})
    skills = surface.get("skills", [])
    if "rabbit-issue" not in skills:
        fails.append(f"surface.skills must contain 'rabbit-issue', got {skills!r}")

    scripts = surface.get("scripts", [])
    for script in EXPECTED_SCRIPTS:
        if script not in scripts:
            fails.append(f"surface.scripts missing {script!r}")

    manifest = data.get("manifest", [])
    if not any(
        isinstance(m, dict) and m.get("api") == "publish_skill"
        and m.get("args", {}).get("source") == "skills/rabbit-issue/SKILL.md"
        for m in manifest
    ):
        fails.append(
            "manifest must include publish_skill entry for "
            "skills/rabbit-issue/SKILL.md"
        )

    if fails:
        for msg in fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-manifest-shape")
    return 0


if __name__ == "__main__":
    sys.exit(main())
