#!/usr/bin/env python3
"""test-plan-batch.py — e2e tests for scripts/plan-batch.py (Inv 4).

Covers the spec-mandated scenarios for the conflict-graph + barrier
dispatch planner:
  - --help smoke test
  - Contract-only set: all items land in barrier_first (sorted), groups
    is empty.
  - Same-feature set: graph coloring forces each item into its own
    group.
  - Mixed-feature set: all items can co-exist in a single group.
  - Over-cap set: a group whose size exceeds --max-parallel is split
    into sub-groups of size <= cap.
  - --max-parallel validation: non-integer / <1 values exit non-zero.

The script is a pure JSON processor (no gh, no fs); tests build small
fixture dicts inline and pipe them via subprocess stdin.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "plan-batch.py"))

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def run_plan(items, extra_args=None):
    """Invoke plan-batch.py with `items` piped as JSON on stdin."""
    args = [sys.executable, SCRIPT]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(
        args,
        input=json.dumps(items),
        capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# --help smoke test
# ---------------------------------------------------------------------------
proc = subprocess.run(
    [sys.executable, SCRIPT, "--help"],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    fail(f"help: --help exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    ok("help: --help exited 0")
help_text = (proc.stdout + proc.stderr).lower()
if "usage" not in help_text:
    fail(f"help: expected 'usage' in output; got {proc.stdout!r} {proc.stderr!r}")
else:
    ok("help: 'usage' in output")


# ---------------------------------------------------------------------------
# Scenario 1 — Contract-only set
#   All items have contract_touch=true; expect them all in barrier_first,
#   sorted by priority desc then issue asc; groups must be [].
# ---------------------------------------------------------------------------
items = [
    {"issue": 305, "feature": "contract", "contract_touch": True, "priority": "low"},
    {"issue": 300, "feature": "contract", "contract_touch": True, "priority": "critical"},
    {"issue": 310, "feature": "contract", "contract_touch": True, "priority": "high"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"contract-only: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        # critical (300) before high (310) before low (305)
        want_barrier = [300, 310, 305]
        if out.get("barrier_first") != want_barrier:
            fail(f"contract-only: barrier_first={out.get('barrier_first')!r}, want {want_barrier!r}")
        elif out.get("groups") != []:
            fail(f"contract-only: groups should be empty, got {out.get('groups')!r}")
        else:
            ok("contract-only: barrier_first sorted, groups empty")
    except json.JSONDecodeError as e:
        fail(f"contract-only: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 2 — Same-feature set (no contract)
#   3 items share feature 'F'; graph coloring forces 3 separate groups.
# ---------------------------------------------------------------------------
items = [
    {"issue": 401, "feature": "F", "contract_touch": False, "priority": "high"},
    {"issue": 402, "feature": "F", "contract_touch": False, "priority": "medium"},
    {"issue": 403, "feature": "F", "contract_touch": False, "priority": "low"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"same-feature: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        if out.get("barrier_first") != []:
            fail(f"same-feature: barrier_first should be empty, got {out.get('barrier_first')!r}")
        groups = out.get("groups", [])
        if len(groups) != 3:
            fail(f"same-feature: expected 3 groups, got {len(groups)}: {groups!r}")
        elif not all(len(g) == 1 for g in groups):
            fail(f"same-feature: each group should hold one item, got {groups!r}")
        else:
            # Higher priority should color first.
            if groups[0] != [401]:
                fail(f"same-feature: group[0] should be [401] (highest priority), got {groups[0]!r}")
            else:
                ok("same-feature: 3 groups, one item each, priority order honored")
    except json.JSONDecodeError as e:
        fail(f"same-feature: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 3 — Mixed-feature set (no contract)
#   3 items have distinct features; no conflict edges; expect 1 group of 3.
# ---------------------------------------------------------------------------
items = [
    {"issue": 501, "feature": "Fa", "contract_touch": False, "priority": "high"},
    {"issue": 502, "feature": "Fb", "contract_touch": False, "priority": "medium"},
    {"issue": 503, "feature": "Fc", "contract_touch": False, "priority": "low"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"mixed-feature: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        groups = out.get("groups", [])
        if len(groups) != 1:
            fail(f"mixed-feature: expected 1 group, got {len(groups)}: {groups!r}")
        elif sorted(groups[0]) != [501, 502, 503]:
            fail(f"mixed-feature: group should contain {{501,502,503}}, got {groups[0]!r}")
        else:
            ok("mixed-feature: single group containing all 3 distinct-feature items")
    except json.JSONDecodeError as e:
        fail(f"mixed-feature: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 4 — Over-cap set
#   8 distinct-feature non-contract items with --max-parallel 3 must split
#   into sub-groups of size <= 3 (e.g. 3/3/2).
# ---------------------------------------------------------------------------
items = [
    {"issue": 600 + i, "feature": f"F{i}", "contract_touch": False, "priority": "medium"}
    for i in range(8)
]
proc = run_plan(items, ["--max-parallel", "3"])
if proc.returncode != 0:
    fail(f"over-cap: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        groups = out.get("groups", [])
        sizes = [len(g) for g in groups]
        if any(s > 3 for s in sizes):
            fail(f"over-cap: a group exceeds cap=3; sizes={sizes}")
        elif sum(sizes) != 8:
            fail(f"over-cap: total items != 8; sizes={sizes}, groups={groups!r}")
        elif sizes != [3, 3, 2]:
            # Stronger assertion: spec gives the exact expected split.
            fail(f"over-cap: expected sizes [3, 3, 2], got {sizes}")
        else:
            ok("over-cap: 8 items split into [3, 3, 2] sub-groups under cap=3")
    except json.JSONDecodeError as e:
        fail(f"over-cap: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 5 — --max-parallel validation
#   Non-integer and <1 values must exit non-zero.
# ---------------------------------------------------------------------------
proc = run_plan([], ["--max-parallel", "0"])
if proc.returncode == 0:
    fail("max-parallel-zero: should exit non-zero on N<1")
else:
    ok("max-parallel-zero: exited non-zero")

proc = run_plan([], ["--max-parallel", "-1"])
if proc.returncode == 0:
    fail("max-parallel-negative: should exit non-zero on N<1")
else:
    ok("max-parallel-negative: exited non-zero")

proc = run_plan([], ["--max-parallel", "abc"])
if proc.returncode == 0:
    fail("max-parallel-noninteger: should exit non-zero on non-integer")
else:
    ok("max-parallel-noninteger: exited non-zero")


# ---------------------------------------------------------------------------
# Scenario 6 — Combined: contract + non-contract mix
#   Verify barrier_first is independent from groups, both populated.
# ---------------------------------------------------------------------------
items = [
    {"issue": 701, "feature": "contract", "contract_touch": True, "priority": "high"},
    {"issue": 702, "feature": "Fx", "contract_touch": False, "priority": "high"},
    {"issue": 703, "feature": "Fy", "contract_touch": False, "priority": "medium"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"combined: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        if out.get("barrier_first") != [701]:
            fail(f"combined: barrier_first={out.get('barrier_first')!r}, want [701]")
        groups = out.get("groups", [])
        if len(groups) != 1 or sorted(groups[0]) != [702, 703]:
            fail(f"combined: expected single group [702,703], got {groups!r}")
        else:
            ok("combined: barrier_first=[701], groups=[[702,703]]")
    except json.JSONDecodeError as e:
        fail(f"combined: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 7 — Unfiltered triage array (Inv 4 update + Inv 18 pipe)
#   Mixed [work, close-not-planned, defer] items: plan-batch silently drops
#   anything whose decision != "work" so the standard pipe
#   `fetch-queue | triage-batch | plan-batch` passes the unfiltered triage
#   output through cleanly.
# ---------------------------------------------------------------------------
items = [
    {"issue": 801, "feature": "Fa", "contract_touch": False, "priority": "high",
     "decision": "work"},
    {"issue": 802, "feature": "Fb", "contract_touch": False, "priority": "high",
     "decision": "close-not-planned"},
    {"issue": 803, "feature": "Fc", "contract_touch": False, "priority": "medium",
     "decision": "defer"},
    {"issue": 804, "feature": "Fd", "contract_touch": True, "priority": "high",
     "decision": "work"},
    {"issue": 805, "feature": "Fe", "contract_touch": True, "priority": "high",
     "decision": "defer"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"unfiltered-triage: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        # Only 801 (work) and 804 (work, contract) should survive.
        if out.get("barrier_first") != [804]:
            fail(f"unfiltered-triage: barrier_first={out.get('barrier_first')!r}, "
                 f"want [804] (805 deferred + dropped)")
        groups = out.get("groups", [])
        if len(groups) != 1 or sorted(groups[0]) != [801]:
            fail(f"unfiltered-triage: expected groups=[[801]], got {groups!r}")
        else:
            ok("unfiltered-triage: non-work items silently dropped; only 801+804 survive")
    except json.JSONDecodeError as e:
        fail(f"unfiltered-triage: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 8 — Items WITHOUT decision field should still be processed.
#   Backwards-compat: callers that pre-filter to work-only and omit the
#   decision field continue to work.
# ---------------------------------------------------------------------------
items = [
    {"issue": 901, "feature": "Fa", "contract_touch": False, "priority": "high"},
    {"issue": 902, "feature": "Fb", "contract_touch": False, "priority": "medium"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"no-decision-field: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        groups = out.get("groups", [])
        if len(groups) != 1 or sorted(groups[0]) != [901, 902]:
            fail(f"no-decision-field: expected single group [901,902], got {groups!r}")
        else:
            ok("no-decision-field: items without decision field still processed")
    except json.JSONDecodeError as e:
        fail(f"no-decision-field: bad JSON ({e}); stdout={proc.stdout!r}")


sys.exit(FAIL)
