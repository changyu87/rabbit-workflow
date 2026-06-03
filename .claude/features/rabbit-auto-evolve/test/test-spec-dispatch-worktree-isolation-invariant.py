#!/usr/bin/env python3
"""test-spec-dispatch-worktree-isolation-invariant.py — rabbit-auto-evolve
Inv 28 (issue #430).

Asserts the dispatch-worktree-isolation invariant text is present in BOTH
the feature spec (specs/spec.md, dual-read with docs/spec/ fallback per
issue #399) AND the deployed/source SKILL.md. The invariant mandates that
EVERY Agent call for a TDD-subagent dispatch in phase 5 MUST include the
`isolation: "worktree"` parameter, because parallel TDD subagents that
share the dispatcher's single git working directory collide on branch
checkout, HEAD, commits, and scope markers.

Owner: rabbit-workflow team (rabbit-auto-evolve)
Version: 1.0.0
Deprecation criterion: removed when Claude Code's Agent tool defaults
  every TDD-subagent dispatch to an isolated worktree and the explicit
  isolation parameter is no longer load-bearing.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# Dual-read (issue #399): prefer specs/spec.md, fall back to docs/spec/spec.md.
SPEC_MD = (FEATURE_DIR / "specs" / "spec.md")
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

# The skill is published from skills/rabbit-auto-evolve/SKILL.md (source) to
# .claude/skills/rabbit-auto-evolve/SKILL.md (deployed) by the publish_skill
# manifest entry. Both must carry the isolation requirement.
SKILL_SRC = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
REPO_ROOT = FEATURE_DIR.parents[2]  # .../<root> from .claude/features/<name>
SKILL_DEPLOYED = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def collapse(p):
    return re.sub(r"\s+", " ", p.read_text().lower())


# ---------------------------------------------------------------------------
# Spec — the Inv 28 invariant text.
# ---------------------------------------------------------------------------
spec = collapse(SPEC_MD)

SPEC_REQUIRED = [
    # The load-bearing mandate: every TDD dispatch Agent call uses worktree
    # isolation.
    'isolation: "worktree"',
    "every agent call for a tdd-subagent dispatch",
    # It is a DISPATCHER policy, not a subagent policy.
    "dispatcher policy, not a subagent policy",
    # The failure being prevented (branch/HEAD/commit/scope-marker collision).
    "shared git working directory",
    # Worktrees branch from dev HEAD (worktree.baseRef: "head"), and the known
    # stale-base / restart limitation is documented.
    "worktree.baseref",
    "requires a session restart",
]

missing = [s for s in SPEC_REQUIRED if s not in spec]
if missing:
    fail(f"spec.md missing dispatch-worktree-isolation phrase(s): {missing!r}")
else:
    ok("spec.md carries the dispatch-worktree-isolation invariant (Inv 28)")


# ---------------------------------------------------------------------------
# SKILL.md (source + deployed) — the phase-5 dispatch isolation requirement.
# ---------------------------------------------------------------------------
SKILL_REQUIRED = [
    'isolation: "worktree"',
    "every agent call for a tdd-subagent dispatch",
]

for label, path in (("source", SKILL_SRC), ("deployed", SKILL_DEPLOYED)):
    if not path.is_file():
        fail(f"SKILL.md ({label}) not found at {path}")
        continue
    body = collapse(path)
    miss = [s for s in SKILL_REQUIRED if s not in body]
    if miss:
        fail(f"SKILL.md ({label}) missing isolation phrase(s): {miss!r}")
    else:
        ok(f"SKILL.md ({label}) documents the worktree-isolation dispatch rule")

sys.exit(FAIL)
