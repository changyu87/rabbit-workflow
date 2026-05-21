#!/usr/bin/env python3
"""Tests /rabbit-config command file is absent (Inv 20 inverted) and that the
old /rabbit-set-threshold command file does not exist (Inv 21)."""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
COMMANDS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/commands")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-rabbit-config.py")

cfg_md = os.path.join(COMMANDS_DIR, "rabbit-config.md")
deployed_cfg_md = os.path.join(REPO_ROOT, ".claude/commands/rabbit-config.md")

# t1 (Inv 20 inverted): rabbit-config.md must NOT exist in source commands/.
if not os.path.lexists(cfg_md):
    ok(1, "rabbit-config.md does not exist in commands/ (Inv 20)")
else:
    fail_t(1, "rabbit-config.md exists in commands/ (Inv 20 forbids it)")

# t2 (Inv 21): rabbit-set-threshold.md must not exist.
if not os.path.lexists(os.path.join(COMMANDS_DIR, "rabbit-set-threshold.md")):
    ok(2, "rabbit-set-threshold.md does not exist in commands/ (old command removed)")
else:
    fail_t(2, "rabbit-set-threshold.md still exists in commands/ (must be removed)")

# t3 (Inv 20 inverted): deployed copy must NOT exist either.
if not os.path.lexists(deployed_cfg_md):
    ok(3, "deployed .claude/commands/rabbit-config.md does not exist (Inv 20)")
else:
    fail_t(3, "deployed .claude/commands/rabbit-config.md exists (Inv 20 forbids it)")

# t4 (BUG-86: schema-level assertion). The prior check iterated cmds looking
# for a "rabbit-set-threshold" substring, which passed vacuously when
# surface.commands == [] (the current contract state per Inv 24). Assert the
# schema directly: surface.commands MUST be exactly [].
feature_json = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/feature.json")
if os.path.isfile(feature_json):
    try:
        with open(feature_json) as f:
            d = json.load(f)
        cmds = d.get("surface", {}).get("commands", [])
        if cmds == []:
            ok(4, "feature.json surface.commands == [] (Inv 24; no stale rabbit-set-threshold could survive)")
        else:
            fail_t(4, f"feature.json surface.commands is not [] (got {cmds!r}) — Inv 24 violated")
    except Exception as e:
        fail_t(4, f"feature.json could not be parsed: {e}")
else:
    fail_t(4, "feature.json not found")

# Prompt-threshold subcommand behaviour is exercised end-to-end in
# test-BACKLOG-11-rabbit-config-skill.py (t7) via the skill script. No
# duplicate coverage here.

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
