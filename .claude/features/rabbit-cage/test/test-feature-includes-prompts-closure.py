#!/usr/bin/env python3
"""rabbit-cage Inv 23 — FEATURE_INCLUDES['contract'] prompt-template closure.

For every skill shipped via install.py's SKILLS list and every subagent
shipped via install.py's AGENTS list, the corresponding prompt template at
`templates/prompts/<id>.txt` (where <id> is the `prompts[].id` declared in
the owning feature's feature.json) MUST appear in
FEATURE_INCLUDES['contract'] AND MUST exist on disk at the source path
`.claude/features/contract/templates/prompts/<id>.txt`.

Skills/subagents whose owning feature.json has no matching prompts entry
are skipped (not every shipped skill registers a prompt).

Failures name the (deployed-name, owning-feature, missing-template) triple
so the fix is mechanical: extend FEATURE_INCLUDES['contract'].
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")
INSTALL_PY = os.path.join(CAGE_DIR, "install.py")

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


print("test-feature-includes-prompts-closure.py")


def load_install_module():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def feature_dir_from_src(src_rel: str) -> str | None:
    """Given a SKILLS or AGENTS source path like
    `.claude/features/<feature>/skills/<name>/SKILL.md` or
    `.claude/features/<feature>/agents/<name>.md`, return the absolute
    feature directory path, or None if the shape is unrecognised."""
    parts = src_rel.split("/")
    if len(parts) < 3 or parts[0] != ".claude" or parts[1] != "features":
        return None
    return os.path.join(REPO_ROOT, ".claude/features", parts[2])


def deployed_name(src_rel: str, kind: str) -> str | None:
    """Extract the skill or subagent name from the source path."""
    parts = src_rel.split("/")
    if kind == "skill":
        # .../skills/<name>/SKILL.md
        if "skills" in parts:
            i = parts.index("skills")
            if i + 1 < len(parts):
                return parts[i + 1]
    elif kind == "subagent":
        # .../agents/<name>.md
        if "agents" in parts:
            i = parts.index("agents")
            if i + 1 < len(parts):
                fname = parts[i + 1]
                if fname.endswith(".md"):
                    return fname[:-3]
                return fname
    return None


def find_prompt_id(feature_dir: str, deployed: str, kind: str) -> str | None:
    """Walk the feature's prompts array; return the id of the entry whose
    `kind` matches and whose id matches the deployed name. Returns None if
    no such entry exists (skill/subagent has no registered prompt)."""
    fj = os.path.join(feature_dir, "feature.json")
    if not os.path.isfile(fj):
        return None
    try:
        with open(fj) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    prompts = data.get("prompts") or []
    for entry in prompts:
        if not isinstance(entry, dict):
            continue
        if entry.get("kind") != kind:
            continue
        pid = entry.get("id")
        if pid == deployed:
            return pid
    return None


mod = load_install_module()
includes: dict[str, list[str]] = getattr(mod, "FEATURE_INCLUDES", {})
contract_includes = set(includes.get("contract", []))
skills: list[tuple[str, str]] = getattr(mod, "SKILLS", [])
agents: list[tuple[str, str]] = getattr(mod, "AGENTS", [])

if not contract_includes:
    fail_t(1, "FEATURE_INCLUDES['contract'] is empty or missing")
else:
    ok(1, f"FEATURE_INCLUDES['contract'] loaded ({len(contract_includes)} paths)")

t = 2


def check_entry(src_rel: str, kind: str) -> None:
    global t
    fdir = feature_dir_from_src(src_rel)
    if fdir is None:
        fail_t(t, f"unrecognised source path shape: {src_rel!r}")
        t += 1
        return
    deployed = deployed_name(src_rel, kind)
    if deployed is None:
        fail_t(t, f"cannot extract {kind} name from {src_rel!r}")
        t += 1
        return
    pid = find_prompt_id(fdir, deployed, kind)
    if pid is None:
        # No registered prompt for this skill/subagent — skip (not a failure)
        ok(t, f"{kind} {deployed!r}: no prompts entry in {os.path.basename(fdir)}/feature.json (skip)")
        t += 1
        return
    rel_template = f"templates/prompts/{pid}.txt"
    on_disk = os.path.join(REPO_ROOT, ".claude/features/contract", rel_template)
    if rel_template not in contract_includes:
        fail_t(t, f"{kind} {deployed!r} (owner={os.path.basename(fdir)}): {rel_template!r} not in FEATURE_INCLUDES['contract']")
        t += 1
        return
    if not os.path.isfile(on_disk):
        fail_t(t, f"{kind} {deployed!r} (owner={os.path.basename(fdir)}): source template missing on disk: {on_disk}")
        t += 1
        return
    ok(t, f"{kind} {deployed!r}: template {rel_template!r} present in includes and on disk")
    t += 1


for src_rel, _dst_rel in skills:
    check_entry(src_rel, "skill")

for src_rel, _dst_rel in agents:
    check_entry(src_rel, "subagent")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
