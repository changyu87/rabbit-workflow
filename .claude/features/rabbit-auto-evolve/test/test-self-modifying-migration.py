#!/usr/bin/env python3
"""test-self-modifying-migration.py — e2e tests for self-modifying-migration
safe-execution patterns (issue #450).

A self-modifying migration is a work item that changes something the loop
itself depends on at runtime. plan-batch.py (Stage-2 dispatch classifier)
detects such items and tags the safe-execution pattern chosen by HOW the loop
consumes the thing:

  re-read from disk each tick  -> coexistence-window  (no restart)
  self-contained               -> last-tick-action    (no restart)
  held in session memory       -> restart-safe        (restart NEXT session)

End-to-end assertions (acceptance criteria 2, 4, 5):
  - an item renaming a disk-read marker -> coexistence-window;
  - an item moving resolved paths -> last-tick-action (or coexistence);
  - an item renaming an in-memory agent type -> restart-safe, and ONLY this one
    is flagged restart_needed;
  - in all three, the planner emits NO human-facing a/b/c question and writes
    NO marker (it is a pure JSON processor).
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.normpath(os.path.join(HERE, "..", "scripts", "plan-batch.py"))
RESTART_MARKER = ".rabbit-auto-evolve-restart-needed"

VALID_PATTERNS = {"coexistence-window", "last-tick-action", "restart-safe"}

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run_plan(items, cwd):
    proc = subprocess.run(
        [sys.executable, PLAN], input=json.dumps(items),
        capture_output=True, text=True, cwd=cwd,
    )
    if proc.returncode != 0:
        fail(f"plan-batch exit {proc.returncode}; stderr={proc.stderr!r}")
        return None, proc
    try:
        return json.loads(proc.stdout), proc
    except json.JSONDecodeError as e:
        fail(f"bad JSON ({e}); stdout={proc.stdout!r}")
        return None, proc


# Each scenario runs in its own temp cwd so we can assert the planner writes no
# restart-needed marker (it is a pure processor; the marker is set by the tick
# driver, not the planner).
tmp = tempfile.mkdtemp()

# ---------------------------------------------------------------------------
# Scenario 1 — renaming a disk-read marker -> coexistence-window; no restart.
# ---------------------------------------------------------------------------
items = [{
    "issue": 901, "feature": "rabbit-auto-evolve",
    "features": ["rabbit-auto-evolve"], "contract_touch": False,
    "priority": "high", "decision": "work",
    "title": "rename the .rabbit-auto-evolve-running marker",
    "body": "Rename the disk-read marker .rabbit-auto-evolve-running to a new "
            "name; the tick driver re-reads it each tick.",
}]
out, _ = run_plan(items, tmp)
if out is not None:
    smm = out.get("self_modifying_migrations", {})
    if smm.get("901") != "coexistence-window":
        fail(f"scenario1: item 901 pattern = {smm.get('901')!r}, "
             f"want coexistence-window; smm={smm!r}")
    else:
        ok("disk-read marker rename -> coexistence-window")
    if 901 in out.get("restart_needed", []):
        fail("scenario1: coexistence item must NOT be flagged restart_needed")
    else:
        ok("disk-read marker rename does NOT request restart")

# ---------------------------------------------------------------------------
# Scenario 2 — moving resolved paths -> last-tick-action (or coexistence);
#              no restart.
# ---------------------------------------------------------------------------
items = [{
    "issue": 902, "feature": "rabbit-auto-evolve",
    "features": ["rabbit-auto-evolve"], "contract_touch": False,
    "priority": "high", "decision": "work",
    "title": "move resolved script paths",
    "body": "Move the resolved path .claude/features/rabbit-auto-evolve/"
            "scripts/log-path.py the loop resolves; later steps in the same "
            "tick must not trip on the half-migrated layout.",
    "self_contained": True,
}]
out, _ = run_plan(items, tmp)
if out is not None:
    smm = out.get("self_modifying_migrations", {})
    if smm.get("902") not in ("last-tick-action", "coexistence-window"):
        fail(f"scenario2: item 902 pattern = {smm.get('902')!r}, "
             f"want last-tick-action or coexistence-window")
    else:
        ok("resolved-path move -> last-tick-action / coexistence-window")
    if 902 in out.get("restart_needed", []):
        fail("scenario2: resolved-path move must NOT be flagged restart_needed")
    else:
        ok("resolved-path move does NOT request restart")

# ---------------------------------------------------------------------------
# Scenario 3 — renaming an in-memory agent type -> restart-safe; restart IS
#              requested; tick still ends cleanly (planner exits 0, no prompt).
# ---------------------------------------------------------------------------
items = [{
    "issue": 903, "feature": "rabbit-auto-evolve",
    "features": ["rabbit-auto-evolve"], "contract_touch": False,
    "priority": "high", "decision": "work",
    "title": "rename the tdd-subagent agent type",
    "body": "Rename the tdd-subagent agent type the loop dispatches; it is "
            "held in session memory loaded at session start.",
}]
out, _ = run_plan(items, tmp)
if out is not None:
    smm = out.get("self_modifying_migrations", {})
    if smm.get("903") != "restart-safe":
        fail(f"scenario3: item 903 pattern = {smm.get('903')!r}, "
             f"want restart-safe; smm={smm!r}")
    else:
        ok("in-memory agent-type rename -> restart-safe")
    if 903 not in out.get("restart_needed", []):
        fail("scenario3: restart-safe item MUST be flagged restart_needed")
    else:
        ok("in-memory agent-type rename requests restart")

# ---------------------------------------------------------------------------
# Combined batch — only the restart-safe item is flagged; planner writes no
# marker and emits no human a/b/c question anywhere in its output.
# ---------------------------------------------------------------------------
batch = [
    {"issue": 901, "feature": "rabbit-auto-evolve",
     "features": ["rabbit-auto-evolve"], "contract_touch": False,
     "priority": "high", "decision": "work",
     "title": "rename marker",
     "body": "rename disk-read marker .rabbit-auto-evolve-running"},
    {"issue": 902, "feature": "rabbit-auto-evolve",
     "features": ["rabbit-auto-evolve"], "contract_touch": False,
     "priority": "high", "decision": "work",
     "title": "move path",
     "body": "move resolved path .claude/features/rabbit-auto-evolve/"
             "scripts/log-path.py",
     "self_contained": True},
    {"issue": 903, "feature": "rabbit-auto-evolve",
     "features": ["rabbit-auto-evolve"], "contract_touch": False,
     "priority": "high", "decision": "work",
     "title": "rename agent type",
     "body": "rename the tdd-subagent agent type held in session memory"},
    # A plain non-self-modifying item is NOT tagged.
    {"issue": 904, "feature": "rabbit-auto-evolve",
     "features": ["rabbit-auto-evolve"], "contract_touch": False,
     "priority": "low", "decision": "work",
     "title": "fix a typo", "body": "fix a docstring typo"},
]
out, proc = run_plan(batch, tmp)
if out is not None:
    smm = out.get("self_modifying_migrations", {})
    if "904" in smm:
        fail(f"combined: non-self-modifying 904 must not be tagged; smm={smm!r}")
    else:
        ok("non-self-modifying item is not tagged")
    restart = set(map(str, out.get("restart_needed", [])))
    if restart != {"903"}:
        fail(f"combined: restart_needed must be exactly {{903}}; got {restart!r}")
    else:
        ok("only the restart-safe item requests restart; tick ends cleanly")
    # Pattern values are always one of the three valid patterns.
    bad = set(smm.values()) - VALID_PATTERNS
    if bad:
        fail(f"combined: invalid pattern(s) emitted: {bad!r}")
    else:
        ok("all emitted patterns are valid")
    # No human-facing a/b/c question in the planner output, and no free-form
    # escalation token (the one yield point is the restart marker, never a
    # human stop).
    raw = (proc.stdout + proc.stderr).lower()
    for forbidden in ("(a)", "(b)", "(c)", "askuserquestion",
                      "escalate to human", "ask the human"):
        if forbidden in raw:
            fail(f"combined: planner emitted human-facing token {forbidden!r}")
            break
    else:
        ok("planner emits no human-facing a/b/c question")

# The planner is a pure processor: it MUST NOT write the restart-needed marker.
if os.path.exists(os.path.join(tmp, RESTART_MARKER)):
    fail("planner wrote the restart-needed marker (must be a pure processor)")
else:
    ok("planner writes no restart-needed marker")

import shutil
shutil.rmtree(tmp, ignore_errors=True)

sys.exit(FAIL)
