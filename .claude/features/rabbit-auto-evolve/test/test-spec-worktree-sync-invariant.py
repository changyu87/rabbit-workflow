#!/usr/bin/env python3
"""test-spec-worktree-sync-invariant.py — rabbit-auto-evolve Inv 38 (#524).

Inv 38 introduces a tick-start working-tree self-sync (`scripts/sync-tree.py`
running `git pull --ff-only origin dev`) so the loop runs the LATEST merged
scripts instead of stale ones, never using the permission-denied `git merge`.

This e2e regression asserts:

  1. The spec carries the Inv 38 text (issue #524 cross-ref, the
     `sync-tree.py` script, `git pull --ff-only origin dev`, the clean-tree
     precondition, and the explicit "never git merge" constraint).
  2. BOTH SKILL.md copies (source + deployed) document the tick-start
     `sync-tree.py` step using `git pull --ff-only`, and contain NO
     `git merge` sync instruction.
  3. tick-headless.py invokes sync-tree.py (the headless path self-syncs too).
  4. All four versioned artifacts (feature.json, spec.md, contract.md,
     SKILL.md frontmatter) are bumped in lockstep to the SAME version
     (Inv 15).
"""

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]


def _resolve_doc(name):
    """Dual-read (issue #399): prefer the flat docs/<name> layout, fall back
    to specs/<name>, then legacy docs/spec/<name>."""
    for candidate in (
        FEATURE_DIR / "docs" / name,
        FEATURE_DIR / "specs" / name,
        FEATURE_DIR / "docs" / "spec" / name,
    ):
        if candidate.is_file():
            return candidate
    return FEATURE_DIR / "docs" / name


SPEC_MD = _resolve_doc("spec.md")
CONTRACT_MD = _resolve_doc("contract.md")
FEATURE_JSON = FEATURE_DIR / "feature.json"
TICK_HEADLESS = FEATURE_DIR / "scripts" / "tick-headless.py"

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


# --- (1) Spec carries Inv 38 ------------------------------------------
spec_raw = SPEC_MD.read_text()
spec = norm(spec_raw)
spec_low = spec.lower()

SPEC_REQUIRED = [
    "524",
    "sync-tree.py",
    "git pull --ff-only origin dev",
    "git merge",
]
missing = [s for s in SPEC_REQUIRED if s.lower() not in spec_low]
if missing:
    fail(f"spec.md missing Inv 38 phrase(s): {missing!r}")
else:
    ok("spec.md carries the tick-start working-tree self-sync invariant (Inv 38)")

# The numbered invariant header MUST be present.
if re.search(r"(?m)^38\.\s", spec_raw):
    ok("spec.md has the numbered Inv 38 header")
else:
    fail("spec.md missing the numbered '38.' invariant header")


# --- (2) BOTH SKILL.md copies document the sync step, no git-merge sync ----
def check_skill(path, label):
    if not path.is_file():
        fail(f"{label} SKILL.md not found at {path}")
        return
    flat = norm(path.read_text())
    flat_low = flat.lower()
    if "sync-tree.py" not in flat_low:
        fail(f"{label}: SKILL.md does not document the sync-tree.py step")
    else:
        ok(f"{label}: SKILL.md documents the tick-start sync-tree.py step")
    if "git pull --ff-only" not in flat_low:
        fail(f"{label}: SKILL.md does not use 'git pull --ff-only' for the sync")
    else:
        ok(f"{label}: SKILL.md uses 'git pull --ff-only' for the sync")
    # The sync step must NEVER instruct a `git merge`. The only `git merge`
    # mention permitted is the note that it is intentionally DENIED.
    if re.search(r"git merge\s+(--ff-only\s+)?origin/?dev", flat_low):
        fail(f"{label}: SKILL.md contains a 'git merge origin/dev' sync "
             f"instruction (forbidden)")
    else:
        ok(f"{label}: SKILL.md contains no 'git merge origin/dev' sync "
           f"instruction")


check_skill(SOURCE_SKILL, "source")
check_skill(DEPLOYED_SKILL, "deployed")


# --- (3) the headless path self-syncs via sync-tree.py ----------------
# Since Inv 40 (#513) the deterministic phase-walk (including the tick-start
# sync-tree.py call) lives in the shared run-tick-phases.py, which both
# tick-headless.py and the in-session tick invoke. The headless path therefore
# self-syncs either by referencing sync-tree.py directly OR by delegating to
# run-tick-phases.py, whose pre-dispatch segment runs sync-tree.py first.
RUN_TICK_PHASES = FEATURE_DIR / "scripts" / "run-tick-phases.py"
if TICK_HEADLESS.is_file():
    th = TICK_HEADLESS.read_text()
    if "sync-tree.py" in th:
        ok("tick-headless.py invokes sync-tree.py directly (headless path self-syncs)")
    elif "run-tick-phases" in th and RUN_TICK_PHASES.is_file() \
            and "sync-tree.py" in RUN_TICK_PHASES.read_text():
        ok("tick-headless.py self-syncs via the shared run-tick-phases.py walk "
           "(which runs sync-tree.py first)")
    else:
        fail("the headless path does not self-sync via sync-tree.py "
             "(neither directly nor through run-tick-phases.py)")
else:
    fail("tick-headless.py not found")


# --- (4) Lockstep version across the four versioned artifacts ---------
def frontmatter_version(path):
    text = path.read_text()
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$",
                  text, re.MULTILINE)
    return m.group(1) if m else None


fj_version = json.loads(FEATURE_JSON.read_text()).get("version")
spec_version = frontmatter_version(SPEC_MD)
contract_version = frontmatter_version(CONTRACT_MD)
skill_version = frontmatter_version(SOURCE_SKILL)

versions = {
    "feature.json": fj_version,
    "spec.md": spec_version,
    "contract.md": contract_version,
    "SKILL.md": skill_version,
}
if None in versions.values():
    fail(f"could not parse version from all artifacts: {versions!r}")
elif len(set(versions.values())) == 1:
    ok(f"all four versioned artifacts in lockstep at "
       f"{next(iter(versions.values()))} (Inv 15)")
else:
    fail(f"version drift across artifacts: {versions!r}")

sys.exit(FAIL)
