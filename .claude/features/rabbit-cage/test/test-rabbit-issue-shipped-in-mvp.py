#!/usr/bin/env python3
"""rabbit-cage regression — rabbit-issue skill MUST ship in install.py MVP closure.

Bug #260: install.py's MVP file closure omitted the rabbit-issue skill, so
plugin users could not file bugs from inside their project — the very
window in which they are most likely to find them.

Per spec.md Installer Behavior and Inv 23, install.py's SKILLS list MUST
include rabbit-issue alongside the rabbit-feature-* and rabbit-spec-*
skills, FEATURE_INCLUDES MUST carry every runtime source path referenced
by rabbit-issue's manifest (Inv 21), and FEATURE_INCLUDES['contract']
MUST include the corresponding prompt template (Inv 23).

This regression pins all three contracts so a future drop of any one
fails the suite at the install.py module level — without depending on
the cross-feature closure tests catching it transitively.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
INSTALL_PY = os.path.join(REPO_ROOT, "install.py")

REQUIRED_RUNTIME_FILES = [
    "feature.json",
    "skills/rabbit-issue/SKILL.md",
    "scripts/_gh.py",
    "scripts/file-item.py",
    "scripts/item-status.py",
    "scripts/list-items.py",
]

REQUIRED_SKILL_TUPLE = (
    ".claude/features/rabbit-issue/skills/rabbit-issue/SKILL.md",
    ".claude/skills/rabbit-issue/SKILL.md",
)

REQUIRED_PROMPT_TEMPLATE = "templates/prompts/rabbit-issue.txt"

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


def load_install_module():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("test-rabbit-issue-shipped-in-mvp.py")

mod = load_install_module()

# t1 — SKILLS list contains the rabbit-issue tuple.
if REQUIRED_SKILL_TUPLE in getattr(mod, "SKILLS", []):
    ok(1, f"SKILLS contains {REQUIRED_SKILL_TUPLE}")
else:
    fail_t(1, f"SKILLS missing required tuple {REQUIRED_SKILL_TUPLE}")

# t2 — FEATURE_INCLUDES has a 'rabbit-issue' key with all 6 runtime files.
includes = getattr(mod, "FEATURE_INCLUDES", {})
if "rabbit-issue" not in includes:
    fail_t(2, "FEATURE_INCLUDES missing 'rabbit-issue' key")
else:
    listed = set(includes["rabbit-issue"])
    missing = [r for r in REQUIRED_RUNTIME_FILES if r not in listed]
    if missing:
        fail_t(2, f"FEATURE_INCLUDES['rabbit-issue'] missing required runtime files: {missing}")
    else:
        ok(2, f"FEATURE_INCLUDES['rabbit-issue'] contains all {len(REQUIRED_RUNTIME_FILES)} required runtime files")

# t3 — FEATURE_INCLUDES['contract'] contains the rabbit-issue prompt template.
contract_includes = set(includes.get("contract", []))
if REQUIRED_PROMPT_TEMPLATE in contract_includes:
    ok(3, f"FEATURE_INCLUDES['contract'] contains {REQUIRED_PROMPT_TEMPLATE!r}")
else:
    fail_t(3, f"FEATURE_INCLUDES['contract'] missing {REQUIRED_PROMPT_TEMPLATE!r}")

# t4 — Every required runtime file exists on disk at the source path.
feature_root = os.path.join(REPO_ROOT, ".claude/features/rabbit-issue")
t = 4
for rel in REQUIRED_RUNTIME_FILES:
    full = os.path.join(feature_root, rel)
    if os.path.isfile(full):
        ok(t, f"source file present: {full}")
    else:
        fail_t(t, f"source file missing on disk: {full}")
    t += 1

# t_next — The prompt template exists on disk at the contract source path.
prompt_path = os.path.join(REPO_ROOT, ".claude/features/contract", REQUIRED_PROMPT_TEMPLATE)
if os.path.isfile(prompt_path):
    ok(t, f"prompt template present: {prompt_path}")
else:
    fail_t(t, f"prompt template missing on disk: {prompt_path}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
