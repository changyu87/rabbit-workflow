#!/usr/bin/env python3
"""rabbit-cage Inv 38 — every published command file carries the full
required frontmatter (issue #492).

Per spec-rules.md "Skills and commands" + contract/templates/command-template.md,
every rabbit-cage command `.md` deployed via `publish_command` MUST carry YAML
frontmatter with all six required keys:

  name, description, version, owner, deprecation_criterion, template_version

with owner == "rabbit-workflow team" (repo-level rabbit-workflow feature).

This is the gate for #492: rabbit-project.md had NO frontmatter, rabbit-refresh.md
was missing version/owner/deprecation_criterion/template_version, and
rabbit-update.md was missing name/template_version.

Assertions (e2e — drives the real published command files + the real manifest):
  per-command:
    f1  the command file has a YAML frontmatter block.
    f2  the block carries every required key with a non-empty value.
    f3  owner is exactly "rabbit-workflow team".
  closure:
    c1  every publish_command source in feature.json manifest is covered
        by this test (so a newly-added command can't silently skip the gate).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
FEATURE_JSON = os.path.join(CAGE_DIR, "feature.json")

REQUIRED_KEYS = (
    "name",
    "description",
    "version",
    "owner",
    "deprecation_criterion",
    "template_version",
)
REQUIRED_OWNER = "rabbit-workflow team"

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL {t}: {msg}")
    fail_n += 1


def frontmatter_block(text):
    m = re.search(r"(?ms)\A---\s*\n(.*?)\n---\s*\n", text)
    return m.group(1) if m else None


def parse_keys(block):
    """Minimal top-level key:value parse (sufficient for command frontmatter)."""
    out = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


print("test-command-frontmatter-compliance.py")

# Enumerate every publish_command source from the manifest (the gate's input).
data = json.loads(open(FEATURE_JSON).read())
manifest = data.get("manifest") or []
sources = [
    (e.get("args") or {}).get("source")
    for e in manifest
    if e.get("api") == "publish_command"
]
sources = [s for s in sources if s]

if not sources:
    fail_t("c1", "manifest declares no publish_command entries")
else:
    ok("c1", f"manifest declares {len(sources)} publish_command source(s)")

for src in sources:
    path = os.path.join(CAGE_DIR, src)
    base = os.path.basename(src)
    if not os.path.isfile(path):
        fail_t(f"{base}", f"command file missing: {src}")
        continue
    text = open(path).read()
    block = frontmatter_block(text)
    if block is None:
        fail_t(f"{base}.f1", f"{src} has no YAML frontmatter block")
        continue
    ok(f"{base}.f1", f"{src} has a YAML frontmatter block")

    keys = parse_keys(block)
    missing = [k for k in REQUIRED_KEYS if not keys.get(k)]
    if missing:
        fail_t(f"{base}.f2", f"{src} missing/empty required key(s): {missing}")
    else:
        ok(f"{base}.f2", f"{src} carries all required keys")

    owner = keys.get("owner")
    if owner == REQUIRED_OWNER:
        ok(f"{base}.f3", f"{src} owner == {REQUIRED_OWNER!r}")
    else:
        fail_t(f"{base}.f3", f"{src} owner is {owner!r}, expected {REQUIRED_OWNER!r}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
