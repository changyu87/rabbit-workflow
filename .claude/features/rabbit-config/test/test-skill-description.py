#!/usr/bin/env python3
"""test-skill-description.py — Inv 19 (BUG-1 backstop).

The SKILL.md frontmatter description field MUST:
  t19a: be present and non-trivial (>=100 chars)
  t19b: name every subcommand discoverable from the union of all features'
        CONFIGURATION arrays
  t19c: contain the literal '/rabbit-config' trigger phrase
  t19d: contain disambiguation language that overrides the model's default
        interpretation of 'permission bypass' / 'human approval' as
        platform-level concepts (the BUG-1 reopen reason)
"""

import json
import os
import re
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILL_MD = os.path.join(FEATURE_DIR, "skills/rabbit-config/SKILL.md")

import subprocess

result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


def discover_subcommands():
    """Walk every feature.json under .claude/features/, collect subcommand
    strings from configuration entries. Skip retired features."""
    out = []
    if not os.path.isdir(FEATURES_ROOT):
        return out
    for name in sorted(os.listdir(FEATURES_ROOT)):
        fj = os.path.join(FEATURES_ROOT, name, "feature.json")
        if not os.path.isfile(fj):
            continue
        try:
            with open(fj) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or data.get("status") == "retired":
            continue
        for cfg in (data.get("configuration") or []):
            if isinstance(cfg, dict) and cfg.get("subcommand"):
                out.append(cfg["subcommand"])
    return out


def parse_frontmatter(path):
    with open(path) as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return None, content
    fm_block = m.group(1)
    fm = {}
    for line in fm_block.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, content


fm, _ = parse_frontmatter(SKILL_MD)
if fm is None:
    fail("19", f"SKILL.md has no YAML frontmatter: {SKILL_MD}")
    print("test-skill-description: FAIL", file=sys.stderr)
    sys.exit(1)

description = fm.get("description", "")

# t19a: description present, non-trivial
if len(description) < 100:
    fail("19a", f"description too short ({len(description)} chars): {description!r}")
else:
    ok("19a", f"description present ({len(description)} chars)")

# t19b: every discovered subcommand appears in description
subcommands = discover_subcommands()
missing = [s for s in subcommands if s not in description]
if missing:
    fail("19b", f"subcommands missing from description: {missing!r}")
else:
    ok("19b", f"all {len(subcommands)} discovered subcommands named in description")

# t19c: literal '/rabbit-config' trigger phrase
if "/rabbit-config" not in description:
    fail("19c", "description missing literal '/rabbit-config' trigger")
else:
    ok("19c", "description contains '/rabbit-config' trigger")

# t19d: disambiguation language overriding platform-level interpretation
disambig_keywords = ["NOT", "Claude Code permission"]
missing_disambig = [kw for kw in disambig_keywords if kw not in description]
if missing_disambig:
    fail("19d", f"description missing disambiguation keywords: {missing_disambig!r}")
else:
    ok("19d", "description contains disambiguation language (NOT + Claude Code permission)")

if FAIL:
    print("test-skill-description: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-skill-description: all checks passed.")
