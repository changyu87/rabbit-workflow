#!/usr/bin/env python3
"""test-on-off-surface.py — SKILL.md documents `on` and `off` subcommands
as the activation surface for rabbit-auto-evolve (spec Inv 10, Inv 11).

The `on` subcommand invokes scripts/set-evolve-mode.py on and surfaces a
restart instruction inline. The `off` subcommand invokes
scripts/set-evolve-mode.py off.
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
SKILL_PATH = os.path.join(
    REPO_ROOT,
    ".claude/features/rabbit-auto-evolve/skills/rabbit-auto-evolve/SKILL.md",
)


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    if not os.path.isfile(SKILL_PATH):
        fail(f"SKILL.md does not exist at {SKILL_PATH}")

    with open(SKILL_PATH) as f:
        text = f.read()

    # `on` subcommand section.
    on_m = re.search(
        r"(?ms)^###\s+`?on`?\s*$(.+?)(?=^###\s|^##\s|\Z)", text)
    if not on_m:
        fail("SKILL.md missing `### on` subcommand section")
    on_body = on_m.group(1)
    if "set-evolve-mode.py" not in on_body:
        fail("`on` section must mention scripts/set-evolve-mode.py")
    if " on" not in on_body and "`on`" not in on_body:
        fail("`on` section must mention the `on` argv")
    if "restart" not in on_body.lower():
        fail("`on` section must mention restart instruction (case-insensitive)")

    # `off` subcommand section.
    off_m = re.search(
        r"(?ms)^###\s+`?off`?\s*$(.+?)(?=^###\s|^##\s|\Z)", text)
    if not off_m:
        fail("SKILL.md missing `### off` subcommand section")
    off_body = off_m.group(1)
    if "set-evolve-mode.py" not in off_body:
        fail("`off` section must mention scripts/set-evolve-mode.py")
    if " off" not in off_body and "`off`" not in off_body:
        fail("`off` section must mention the `off` argv")

    # Inv 16 — script references MUST use feature-relative prefix.
    # The on/off sections both reference set-evolve-mode.py; that reference
    # MUST carry the full `.claude/features/rabbit-auto-evolve/scripts/`
    # prefix so Claude's path resolution from the deployed SKILL.md
    # (`.claude/skills/rabbit-auto-evolve/SKILL.md`) finds the script.
    feature_prefix = ".claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py"
    if feature_prefix not in on_body:
        fail(
            "Inv 16: `on` section must reference set-evolve-mode.py with the "
            "full `.claude/features/rabbit-auto-evolve/scripts/` prefix"
        )
    if feature_prefix not in off_body:
        fail(
            "Inv 16: `off` section must reference set-evolve-mode.py with the "
            "full `.claude/features/rabbit-auto-evolve/scripts/` prefix"
        )
    # Inv 16 — bare `scripts/set-evolve-mode.py` (not preceded by the
    # feature-relative prefix) is forbidden anywhere in SKILL.md.
    bare_pattern = re.compile(
        r"(?<!\.claude/features/rabbit-auto-evolve/)scripts/set-evolve-mode\.py"
    )
    if bare_pattern.search(text):
        fail(
            "Inv 16: bare `scripts/set-evolve-mode.py` appears in SKILL.md; "
            "every script reference must use the full feature-relative prefix"
        )

    print("PASS: test-on-off-surface.py")


if __name__ == "__main__":
    main()
