#!/usr/bin/env python3
"""BUG-94 e2e tests — stale references cleanup.

Covers:
  t1. test-hook-enforcement.py reads from rabbit-feature, not tdd-subagent (file moved).
  t2. contract.md invokes.scripts does NOT list non-existent .sh files.
  t3. scope-guard.py DENY message does NOT reference dispatch-feature-edit.py.
  t4. contract.md reads.files does NOT list .claude/features/registry.json.
  t5. feature.json summary does NOT mention retired rabbit-bug/rabbit-backlog skills.
  t6. spec.md Inv 40 enumerates repo-permissions.py among scripts/.
  t7. spec.md Inv 40 references a follow-up cycle/backlog for new-feature.py move.
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")

pass_n = 0
fail_n = 0


def ok(n: int, msg: str) -> None:
    global pass_n
    pass_n += 1
    print(f"  PASS t{n}: {msg}")


def fail_t(n: int, msg: str) -> None:
    global fail_n
    fail_n += 1
    print(f"  FAIL t{n}: {msg}")


def read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


print("=== BUG-94 stale-references cleanup ===")

# t1 — test-hook-enforcement.py points at the live skill path
the = read(os.path.join(FEATURE_DIR, "test/test-hook-enforcement.py"))
if "tdd-subagent/skills/rabbit-feature-touch/SKILL.md" in the:
    fail_t(1, "test-hook-enforcement.py still references stale tdd-subagent path")
elif "rabbit-feature/skills/rabbit-feature-touch/SKILL.md" not in the:
    fail_t(1, "test-hook-enforcement.py does not reference rabbit-feature/skills path")
else:
    # Also: the live file must exist where the test now points.
    live = os.path.join(REPO_ROOT, ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md")
    if not os.path.isfile(live):
        fail_t(1, f"rabbit-feature-touch SKILL.md not found at expected live path: {live}")
    else:
        ok(1, "test-hook-enforcement.py points at the current rabbit-feature skill path")

# t2 — contract.md invokes.scripts contains no stale .sh entries
contract = read(os.path.join(FEATURE_DIR, "docs/spec/contract.md"))
if "relink.sh" in contract or "dispatch-feature-edit.sh" in contract:
    fail_t(2, "contract.md still references stale .sh scripts (relink.sh / dispatch-feature-edit.sh)")
else:
    ok(2, "contract.md does not reference stale .sh scripts")

# t3 — scope-guard.py DENY message does not mention dispatch-feature-edit.py
sg = read(os.path.join(FEATURE_DIR, "hooks/scope-guard.py"))
if "dispatch-feature-edit" in sg:
    fail_t(3, "scope-guard.py still references non-existent dispatch-feature-edit script")
else:
    ok(3, "scope-guard.py does not reference dispatch-feature-edit")

# t4 — contract.md reads.files does not list registry.json
if "registry.json" in contract:
    fail_t(4, "contract.md still references non-existent .claude/features/registry.json")
else:
    ok(4, "contract.md does not reference registry.json")

# t5 — feature.json summary does not name retired rabbit-bug / rabbit-backlog skills
feature = json.loads(read(os.path.join(FEATURE_DIR, "feature.json")))
summary = feature.get("summary", "")
if "rabbit-bug" in summary or "rabbit-backlog" in summary:
    fail_t(5, f"feature.json summary still references retired skills: {summary!r}")
else:
    ok(5, "feature.json summary does not name retired rabbit-bug/rabbit-backlog skills")

# t6 — spec.md Inv 40 enumerates repo-permissions.py
spec = read(os.path.join(FEATURE_DIR, "docs/spec/spec.md"))
# locate the Inv 40 paragraph
inv40_match = re.search(r"^40\.\s+.*?(?=^\d+\.\s|\Z)", spec, re.MULTILINE | re.DOTALL)
inv40 = inv40_match.group(0) if inv40_match else ""
if "`repo-permissions.py`" not in inv40:
    fail_t(6, "spec.md Inv 40 does not enumerate repo-permissions.py among scripts/")
else:
    ok(6, "spec.md Inv 40 enumerates repo-permissions.py")

# t7 — spec.md Inv 40 references a follow-up backlog/cycle for new-feature.py move
if not inv40:
    fail_t(7, "Inv 40 not found in spec.md")
elif "new-feature.py" in inv40 and ("BACKLOG" in inv40 or "follow-up cycle" in inv40):
    ok(7, "spec.md Inv 40 references a follow-up cycle/backlog for new-feature.py move")
else:
    fail_t(7, "spec.md Inv 40 does not reference a follow-up cycle/backlog for new-feature.py move")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
