#!/usr/bin/env python3
"""test-skill-no-dead-permissions.py — #366 Part B regression.

rabbit-cage retired the dead `permissions lock|unlock` configurable and
deleted its backing script `repo-permissions.py` (#366 Part A). rabbit-config's
SKILL.md must no longer document that dead subcommand, while continuing to
document every still-active configurable.

CRITICAL: the active `bypass-permissions` configurable (which sets
`permissions.defaultMode`) is load-bearing and MUST remain documented. Only the
dead `permissions lock|unlock` subcommand and its `repo-permissions.py` backing
script are removed.

  t-dead1: SKILL.md contains no `repo-permissions.py` reference.
  t-dead2: SKILL.md contains no `permissions lock` / `permissions unlock`
           dead-subcommand reference (in any spacing/case).
  t-keep1: SKILL.md still documents `bypass-permissions`.
  t-keep2: SKILL.md still documents every other active configurable
           (human-approval, prompt-threshold, allowed-tools, bash-allow).
"""

import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILL_MD = os.path.join(FEATURE_DIR, "skills/rabbit-config/SKILL.md")

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


with open(SKILL_MD) as f:
    content = f.read()

# t-dead1: no repo-permissions.py
if "repo-permissions" in content:
    fail("-dead1", "SKILL.md still references the deleted 'repo-permissions.py' script")
else:
    ok("-dead1", "no repo-permissions.py reference")

# t-dead2: no `permissions lock` / `permissions unlock` dead subcommand.
# Match `permissions` followed (allowing `(` or `|`) by lock/unlock — this
# catches "permissions lock|unlock", "permissions (lock/unlock)",
# "permissions lock", "permissions unlock". Must NOT match "bypass-permissions".
dead_pat = re.compile(r"(?<![\w-])permissions[\s(]+(?:lock|unlock)", re.IGNORECASE)
dead_hits = dead_pat.findall(content)
if dead_hits:
    fail("-dead2", f"SKILL.md still documents dead 'permissions lock|unlock' subcommand: {dead_hits!r}")
else:
    ok("-dead2", "no dead 'permissions lock|unlock' subcommand reference")

# t-keep1: bypass-permissions still documented (load-bearing)
if "bypass-permissions" not in content:
    fail("-keep1", "SKILL.md no longer documents the active 'bypass-permissions' configurable")
else:
    ok("-keep1", "bypass-permissions still documented")

# t-keep2: every other active configurable still documented
required = ["human-approval", "prompt-threshold", "allowed-tools", "bash-allow"]
missing = [c for c in required if c not in content]
if missing:
    fail("-keep2", f"SKILL.md no longer documents active configurables: {missing!r}")
else:
    ok("-keep2", "all other active configurables still documented")

if FAIL:
    print("test-skill-no-dead-permissions: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-skill-no-dead-permissions: all checks passed.")
