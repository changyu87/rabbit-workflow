#!/usr/bin/env python3
"""rabbit-cage Inv 25 — FEATURE_INCLUDES skill-referenced script closure.

For every skill shipped via install.py's SKILLS list, every script that the
SKILL.md body references via a literal path under
`.claude/features/<feature>/scripts/<script>.py` MUST appear in that
feature's FEATURE_INCLUDES[<feature>] list AND MUST exist on disk at the
source path. Transitively, any script that one of THOSE scripts invokes
(subprocess / pipe / exec) — when the invoked script also lives under
`.claude/features/<feature>/scripts/` — MUST likewise appear in
FEATURE_INCLUDES[<feature>].

Failures name the (skill, feature, missing-script) triple so the fix is
mechanical: extend FEATURE_INCLUDES[<feature>].
"""
from __future__ import annotations

import importlib.util
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
INSTALL_PY = os.path.join(CAGE_DIR, "install.py")

# Matches literal paths like .claude/features/<feature>/scripts/<script>.py
SCRIPT_REF_RE = re.compile(
    r"\.claude/features/([\w-]+)/scripts/([\w.-]+\.py)"
)
# Matches sibling-script invocations within a script body, e.g.
#   os.path.join(script_dir, "format-feature-context.py")
#   os.path.join(here, 'other.py')
SIBLING_INVOKE_RE = re.compile(
    r"""os\.path\.join\(\s*[\w_]+\s*,\s*['"]([\w.-]+\.py)['"]\s*\)"""
)

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


print("test-feature-includes-scripts-closure.py")


def load_install_module():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_script_refs(text: str) -> set[tuple[str, str]]:
    """Return set of (feature, script_basename) literal references."""
    return set(SCRIPT_REF_RE.findall(text))


def extract_sibling_invokes(text: str) -> set[str]:
    """Return set of sibling script basenames invoked via
    os.path.join(<dir>, '<script>.py') pattern."""
    return set(SIBLING_INVOKE_RE.findall(text))


mod = load_install_module()
includes: dict[str, list[str]] = getattr(mod, "FEATURE_INCLUDES", {})
skills: list[tuple[str, str]] = getattr(mod, "SKILLS", [])

if not includes:
    fail_t(1, "FEATURE_INCLUDES is empty or missing")
else:
    ok(1, f"FEATURE_INCLUDES loaded ({len(includes)} features)")

if not skills:
    fail_t(2, "SKILLS list is empty or missing")
else:
    ok(2, f"SKILLS loaded ({len(skills)} entries)")

t = 3


def check_script_in_includes(
    feature: str, script_basename: str, label: str,
) -> bool:
    """Assert scripts/<basename> is in FEATURE_INCLUDES[feature] AND exists
    on disk under .claude/features/<feature>/scripts/<basename>.
    Returns True on success, False on failure."""
    global t
    rel = f"scripts/{script_basename}"
    on_disk = os.path.join(
        REPO_ROOT, ".claude/features", feature, "scripts", script_basename,
    )
    feature_includes = set(includes.get(feature, []))
    if feature not in includes:
        fail_t(t, f"{label}: feature {feature!r} has no FEATURE_INCLUDES entry")
        t += 1
        return False
    if rel not in feature_includes:
        fail_t(t, f"{label}: {rel!r} not in FEATURE_INCLUDES[{feature!r}]")
        t += 1
        return False
    if not os.path.isfile(on_disk):
        fail_t(t, f"{label}: source script missing on disk: {on_disk}")
        t += 1
        return False
    ok(t, f"{label}: {rel!r} present in includes and on disk")
    t += 1
    return True


for src_rel, _dst_rel in skills:
    skill_src_abs = os.path.join(REPO_ROOT, src_rel)
    if not os.path.isfile(skill_src_abs):
        fail_t(t, f"skill source missing on disk: {src_rel}")
        t += 1
        continue
    with open(skill_src_abs) as f:
        skill_body = f.read()
    refs = extract_script_refs(skill_body)
    if not refs:
        ok(t, f"skill {src_rel!r}: no literal script references (skip)")
        t += 1
        continue
    for feature, script_basename in sorted(refs):
        label = f"skill {src_rel!r} -> {feature}/{script_basename}"
        if not check_script_in_includes(feature, script_basename, label):
            continue
        # Transitive: read the script body and check sibling invocations.
        script_path = os.path.join(
            REPO_ROOT, ".claude/features", feature, "scripts", script_basename,
        )
        with open(script_path) as sf:
            script_body = sf.read()
        siblings = extract_sibling_invokes(script_body)
        for sib in sorted(siblings):
            if sib == script_basename:
                continue
            sib_label = (
                f"transitive {feature}/{script_basename} -> {feature}/{sib}"
            )
            check_script_in_includes(feature, sib, sib_label)

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
