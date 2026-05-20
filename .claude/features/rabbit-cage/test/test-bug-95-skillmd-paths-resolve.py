#!/usr/bin/env python3
"""Regression test for RABBIT-CAGE-BUG-95.

Spec invariants covered:
- Inv 87 (new): Skills SKILL.md body MUST reference its implementation script(s)
  via the canonical absolute repo-relative path (e.g.
  `.claude/features/<feature>/skills/<skill>/scripts/<script>.py`), NEVER via a
  source-relative path like `scripts/<script>.py`.

Rationale: only SKILL.md is deployed to `.claude/skills/<name>/` (Inv 3); a
source-relative path that worked from the source location fails to resolve from
the deployed location. This test walks every deployed SKILL.md under
`.claude/skills/` and asserts:
  (a) every backticked path token that looks like a script path
      (matches `.claude/.../*.py` or `scripts/...py`) is either absolute
      repo-relative AND resolves to an extant file from REPO_ROOT, OR
  (b) no `scripts/<file>.py`-style source-relative path tokens appear
      anywhere in the body (negative assertion to prevent regression).
"""
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

DEPLOYED_SKILLS_DIR = os.path.join(REPO_ROOT, ".claude/skills")

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


print("test-bug-95-skillmd-paths-resolve.py")

# Discover every deployed SKILL.md
deployed_skill_mds = []
if os.path.isdir(DEPLOYED_SKILLS_DIR):
    for name in sorted(os.listdir(DEPLOYED_SKILLS_DIR)):
        candidate = os.path.join(DEPLOYED_SKILLS_DIR, name, "SKILL.md")
        if os.path.isfile(candidate):
            deployed_skill_mds.append(candidate)

if not deployed_skill_mds:
    fail_t(0, f"no deployed SKILL.md files under {DEPLOYED_SKILLS_DIR}")
else:
    ok(0, f"found {len(deployed_skill_mds)} deployed SKILL.md file(s)")

# Patterns:
#   abs_path  — repo-relative path beginning with ".claude/" ending in .py
#   src_rel   — source-relative path like "scripts/foo.py"
# Path tokens are extracted from backtick-delimited spans (inline code) so
# we ignore prose mentions like "in scripts/...".
BACKTICK_TOKEN = re.compile(r"`([^`\n]+)`")
ABS_PATH = re.compile(r"^\.claude/[^\s`]+\.py$")
SRC_REL = re.compile(r"^scripts/[^\s/`]+\.py$")

t = 1
for skill_md_path in deployed_skill_mds:
    rel = os.path.relpath(skill_md_path, REPO_ROOT)
    with open(skill_md_path) as f:
        body = f.read()

    # Strip YAML frontmatter
    m = re.match(r"^---\n.*?\n---\n", body, re.DOTALL)
    if m:
        body = body[m.end():]

    # Collect backtick tokens that look like paths
    abs_paths = []
    src_rel_paths = []
    for tok in BACKTICK_TOKEN.findall(body):
        tok = tok.strip()
        if ABS_PATH.match(tok):
            abs_paths.append(tok)
        elif SRC_REL.match(tok):
            src_rel_paths.append(tok)

    # Negative assertion: NO source-relative script paths.
    if src_rel_paths:
        fail_t(
            t,
            f"{rel}: forbidden source-relative path tokens (Inv 87): "
            f"{src_rel_paths!r}",
        )
    else:
        ok(t, f"{rel}: no source-relative script-path tokens")
    t += 1

    # Positive assertion: every absolute repo-relative .py path resolves.
    unresolved = [
        p for p in abs_paths
        if not os.path.exists(os.path.join(REPO_ROOT, p))
    ]
    if unresolved:
        fail_t(
            t,
            f"{rel}: absolute repo-relative path token(s) do not resolve: "
            f"{unresolved!r}",
        )
    else:
        ok(
            t,
            f"{rel}: all {len(abs_paths)} absolute repo-relative .py path "
            f"token(s) resolve",
        )
    t += 1

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
