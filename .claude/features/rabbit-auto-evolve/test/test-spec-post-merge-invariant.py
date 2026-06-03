#!/usr/bin/env python3
"""test-spec-post-merge-invariant.py — rabbit-auto-evolve Inv 30 (issue #499).

Phases 7 (release), 8 (cleanup), and 9 (catch-up) were prose in SKILL.md
walked by the LLM orchestrator. After phase 6 (merge) landed a large batch
of PRs, the orchestrator ended the tick for scale/context reasons and phases
7-9 were silently dropped. The fix is the deterministic, non-skippable
run-post-merge.py runner.

This is the end-to-end regression for the fix. It asserts:
  1. The spec carries the Inv 30 text (run-post-merge.py + pending_post_merge).
  2. BOTH the source SKILL.md and the deployed SKILL.md invoke
     run-post-merge.py AFTER the merge phase AND at tick start.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
REPO_ROOT = FEATURE_DIR.parents[2]
DEPLOYED_SKILL = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def norm(text):
    return re.sub(r"\s+", " ", text)


# --- (1) Spec carries Inv 30 -------------------------------------------
spec = norm(SPEC_MD.read_text())
spec_low = spec.lower()

SPEC_REQUIRED = [
    "run-post-merge.py",
    "pending_post_merge",
    "release-bump.py",
    "cleanup-branches.py",
    "classify-merge-restart.py",
    "1.2.0",
    "--record-pending",
    "499",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing post-merge-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the run-post-merge invariant (Inv 30)")


# --- (2) Both SKILL.md copies invoke run-post-merge.py -------------------
def check_skill(path, label):
    if not path.is_file():
        fail(f"{label} SKILL.md not found at {path}")
        return
    body = path.read_text()
    flat = norm(body)
    flat_low = flat.lower()

    if "run-post-merge.py" in flat_low:
        ok(f"{label}: invokes run-post-merge.py")
    else:
        fail(f"{label}: does not invoke run-post-merge.py")
        return

    # The runner must be referenced at least twice: once after the merge
    # phase (post-merge processing) and once at tick start (owed-work drain).
    occurrences = flat_low.count("run-post-merge.py")
    if occurrences >= 2:
        ok(f"{label}: run-post-merge.py referenced >= 2 times "
           f"(after merge + tick-start drain)")
    else:
        fail(f"{label}: run-post-merge.py referenced only {occurrences} "
             f"time(s); expected >= 2 (after merge AND tick start)")

    # The merge phase must record pending PRs via --record-pending.
    if "--record-pending" in flat_low:
        ok(f"{label}: merge phase records pending PRs (--record-pending)")
    else:
        fail(f"{label}: does not document --record-pending on the merge phase")


check_skill(SOURCE_SKILL, "source")
check_skill(DEPLOYED_SKILL, "deployed")

sys.exit(FAIL)
