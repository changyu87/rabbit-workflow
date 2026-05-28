#!/usr/bin/env python3
"""test-deployed-skills-match-source.py — RABBIT-CAGE-BACKLOG-34 / Inv 61.

For every source SKILL.md at .claude/features/*/skills/<name>/SKILL.md, the
deployed copy at .claude/skills/<name>/SKILL.md MUST exist and be
byte-identical. Catches future source-only edits that fail to redeploy.

The check is preventive: when no drift exists, the test passes vacuously.
It FAILs loudly on any missing deployment or byte-difference.

Non-interactive. Exits non-zero on failure.
"""

import glob
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")
DEPLOYED_SKILLS_ROOT = os.path.join(REPO_ROOT, ".claude", "skills")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


sources = sorted(
    glob.glob(os.path.join(FEATURES_ROOT, "*", "skills", "*", "SKILL.md"))
)

if not sources:
    # Vacuous pass — no source SKILL.md files at all is a degenerate state
    # but not a contract violation by this invariant.
    ok("t0", "no source SKILL.md files found — vacuous pass")
    print()
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(0)

ok("t0", f"discovered {len(sources)} source SKILL.md file(s)")

for i, src in enumerate(sources, start=1):
    # Skill name is the directory containing SKILL.md
    skill_name = os.path.basename(os.path.dirname(src))
    deployed = os.path.join(DEPLOYED_SKILLS_ROOT, skill_name, "SKILL.md")
    tid = f"t{i}-{skill_name}"
    if not os.path.isfile(deployed):
        fail(tid, f"deployed copy missing: {deployed} (source: {src})")
        continue
    with open(src, "rb") as f:
        src_bytes = f.read()
    with open(deployed, "rb") as f:
        dep_bytes = f.read()
    if src_bytes != dep_bytes:
        fail(
            tid,
            f"byte-difference between source ({src}) and deployed ({deployed}); "
            f"source={len(src_bytes)} bytes, deployed={len(dep_bytes)} bytes",
        )
    else:
        ok(tid, f"deployed SKILL.md is byte-identical to source")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
