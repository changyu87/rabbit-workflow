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


# ---------------------------------------------------------------------------
# Scenario 9 — Priority over barrier (issue #479)
#   A critical NON-contract item plus a low-priority contract-touch item.
#   Priority is the PRIMARY key: the critical item must lead selection_order
#   and barrier_first must be EMPTY (the low contract item does NOT jump
#   ahead of the critical item).
# ---------------------------------------------------------------------------
items = [
    {"issue": 1001, "feature": "Fcrit", "contract_touch": False, "priority": "critical"},
    {"issue": 1002, "feature": "contract", "contract_touch": True, "priority": "low"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"priority-over-barrier: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        if out.get("selection_order") != [1001, 1002]:
            fail(f"priority-over-barrier: selection_order="
                 f"{out.get('selection_order')!r}, want [1001, 1002]")
        elif out.get("barrier_first") != []:
            fail(f"priority-over-barrier: barrier_first should be empty "
                 f"(critical non-contract leads), got {out.get('barrier_first')!r}")
        else:
            # The low contract item still appears in groups (remainder).
            groups = out.get("groups", [])
            flat = [i for g in groups for i in g]
            if sorted(flat) != [1001, 1002]:
                fail(f"priority-over-barrier: groups should hold both items, "
                     f"got {groups!r}")
            elif flat[0] != 1001:
                fail(f"priority-over-barrier: critical item must be first in "
                     f"group order, got {flat!r}")
            else:
                ok("priority-over-barrier: critical non-contract leads, "
                   "barrier_first empty")
    except json.JSONDecodeError as e:
        fail(f"priority-over-barrier: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 10 — Same-tier barrier tiebreak (issue #479)
#   A contract-touch item and a non-contract item, BOTH high priority.
#   Within the tier the contract item precedes the non-contract item, so it
#   lands in barrier_first.
# ---------------------------------------------------------------------------
items = [
    {"issue": 1101, "feature": "Fx", "contract_touch": False, "priority": "high"},
    {"issue": 1102, "feature": "contract", "contract_touch": True, "priority": "high"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"same-tier-barrier: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        if out.get("barrier_first") != [1102]:
            fail(f"same-tier-barrier: barrier_first={out.get('barrier_first')!r}, "
                 f"want [1102] (contract leads within tier)")
        elif out.get("selection_order") != [1102, 1101]:
            fail(f"same-tier-barrier: selection_order="
                 f"{out.get('selection_order')!r}, want [1102, 1101]")
        else:
            groups = out.get("groups", [])
            if len(groups) != 1 or groups[0] != [1101]:
                fail(f"same-tier-barrier: expected groups=[[1101]], got {groups!r}")
            else:
                ok("same-tier-barrier: contract item leads within tier "
                   "(barrier-as-tiebreak preserved)")
    except json.JSONDecodeError as e:
        fail(f"same-tier-barrier: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 11 — The #463-vs-#469 scenario (issue #479)
#   Critical rabbit-auto-evolve (non-contract) beats a low-priority contract
#   item. Mirrors the real-world dispatch where a critical feature fix was
#   wrongly blocked behind a low contract touch.
# ---------------------------------------------------------------------------
items = [
    {"issue": 469, "feature": "contract", "contract_touch": True, "priority": "low"},
    {"issue": 463, "feature": "rabbit-auto-evolve", "contract_touch": False,
     "priority": "critical"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"463-vs-469: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        if out.get("selection_order") != [463, 469]:
            fail(f"463-vs-469: selection_order={out.get('selection_order')!r}, "
                 f"want [463, 469] (critical beats low contract)")
        elif out.get("barrier_first") != []:
            fail(f"463-vs-469: barrier_first should be empty, got "
                 f"{out.get('barrier_first')!r}")
        else:
            groups = out.get("groups", [])
            flat = [i for g in groups for i in g]
            if flat[:1] != [463]:
                fail(f"463-vs-469: critical #463 must dispatch first, got {flat!r}")
            else:
                ok("463-vs-469: critical rabbit-auto-evolve beats low contract")
    except json.JSONDecodeError as e:
        fail(f"463-vs-469: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 12 — selection_order and barrier_first agree on ordering (#479)
#   Mixed set across tiers; barrier_first must be a leading subsequence of
#   selection_order (no contract item leads barrier_first unless it also
#   leads selection_order).
# ---------------------------------------------------------------------------
items = [
    {"issue": 1201, "feature": "Fa", "contract_touch": False, "priority": "critical"},
    {"issue": 1202, "feature": "contract", "contract_touch": True, "priority": "critical"},
    {"issue": 1203, "feature": "contract", "contract_touch": True, "priority": "low"},
    {"issue": 1204, "feature": "Fb", "contract_touch": False, "priority": "high"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"order-agree: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        bar = out.get("barrier_first", [])
        # Composite key: (priority, contract_touch, issue).
        #   1202 (critical, contract) < 1201 (critical, non) < 1204 (high) < 1203 (low)
        want_sel = [1202, 1201, 1204, 1203]
        if sel != want_sel:
            fail(f"order-agree: selection_order={sel!r}, want {want_sel!r}")
        # barrier_first = leading run of contract items = just [1202]
        elif bar != [1202]:
            fail(f"order-agree: barrier_first={bar!r}, want [1202]")
        elif sel[:len(bar)] != bar:
            fail(f"order-agree: barrier_first {bar!r} is not a leading "
                 f"subsequence of selection_order {sel!r}")
        else:
            ok("order-agree: barrier_first leads selection_order consistently")
    except json.JSONDecodeError as e:
        fail(f"order-agree: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 13 — Research dispatch shape (issue #478)
#   A batch with a research item plus a work item: the research issue appears
#   in selection_order with dispatch_shapes[N]=="research" and N in
#   research_items, and is ABSENT from barrier_first and groups. The work item
#   is unaffected.
# ---------------------------------------------------------------------------
items = [
    {"issue": 1301, "feature": "Fwork", "features": ["Fwork"],
     "contract_touch": False, "priority": "high", "decision": "work"},
    {"issue": 1302, "feature": "Fresearch", "features": ["Fresearch"],
     "contract_touch": False, "priority": "high", "decision": "research"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"research-shape: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        shapes = out.get("dispatch_shapes", {})
        research_items = out.get("research_items")
        groups = out.get("groups", [])
        flat_groups = [i for g in groups for i in g]
        if shapes.get("1302") != "research":
            fail(f"research-shape: dispatch_shapes[1302]={shapes.get('1302')!r}, "
                 f"want 'research'")
        elif research_items != [1302]:
            fail(f"research-shape: research_items={research_items!r}, want [1302]")
        elif 1302 in out.get("barrier_first", []):
            fail("research-shape: research item must not be in barrier_first")
        elif 1302 in flat_groups:
            fail("research-shape: research item must not be in groups")
        elif 1302 not in out.get("selection_order", []):
            fail("research-shape: research item must appear in selection_order")
        # Work item unaffected.
        elif shapes.get("1301") != "parallel-per-feature":
            fail(f"research-shape: work item 1301 shape changed: "
                 f"{shapes.get('1301')!r}")
        elif 1301 not in flat_groups:
            fail("research-shape: work item 1301 must still appear in groups")
        else:
            ok("research-shape: research item routed to 'research' + "
               "research_items, excluded from barrier_first/groups; work "
               "item unaffected")
    except json.JSONDecodeError as e:
        fail(f"research-shape: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 14 — research_items key always present (issue #478)
#   A batch with NO research items still emits a research_items key (empty
#   list), so callers can rely on its presence.
# ---------------------------------------------------------------------------
items = [
    {"issue": 1401, "feature": "Fa", "features": ["Fa"],
     "contract_touch": False, "priority": "high", "decision": "work"},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"research-empty: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        if "research_items" not in out:
            fail("research-empty: research_items key must always be present")
        elif out.get("research_items") != []:
            fail(f"research-empty: research_items should be empty, got "
                 f"{out.get('research_items')!r}")
        else:
            ok("research-empty: research_items key present and empty when no "
               "research items")
    except json.JSONDecodeError as e:
        fail(f"research-empty: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 15 — Loop-computed priority score (issue #441)
#   Two items with IDENTICAL filer priority labels but different
#   blocking-fanout: the issue that more OTHER open items declare a
#   `blocked-by` dependency on must rank FIRST. The loop computes its own
#   priority score from observable signals; the filer label is one input
#   among several, no longer the sole determinant.
#
#   1501 is referenced as a blocker by 1502 and 1503 (fanout=2); 1502 has
#   fanout=0. Both are filed at `priority:high`. The higher-fanout item
#   (1501) must lead selection_order.
# ---------------------------------------------------------------------------
items = [
    {"issue": 1501, "feature": "Fa", "contract_touch": False, "priority": "high",
     "decision": "work", "blocked_by": []},
    {"issue": 1502, "feature": "Fb", "contract_touch": False, "priority": "high",
     "decision": "work", "blocked_by": [1501]},
    {"issue": 1503, "feature": "Fc", "contract_touch": False, "priority": "high",
     "decision": "work", "blocked_by": [1501]},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"fanout-ordering: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        if not sel or sel[0] != 1501:
            fail(f"fanout-ordering: high-fanout #1501 must lead selection_order, "
                 f"got {sel!r}")
        else:
            ok("fanout-ordering: higher blocking-fanout item ranks first within "
               "the same filer-label tier")
    except json.JSONDecodeError as e:
        fail(f"fanout-ordering: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 16 — Bug outranks enhancement across filer labels (issue #441)
#   A `bug` at filer priority:medium with high blocking-fanout outranks an
#   `enhancement` at filer priority:high with no fanout. The loop's computed
#   score dilutes the filer label so a mislabeled-modest foundational bug is
#   not stuck behind an assertively-labeled enhancement.
# ---------------------------------------------------------------------------
items = [
    {"issue": 1601, "feature": "Fa", "contract_touch": False, "priority": "high",
     "decision": "work", "issue_type": "enhancement", "blocked_by": []},
    {"issue": 1602, "feature": "Fb", "contract_touch": False, "priority": "medium",
     "decision": "work", "issue_type": "bug", "blocked_by": []},
    {"issue": 1603, "feature": "Fc", "contract_touch": False, "priority": "low",
     "decision": "work", "issue_type": "enhancement", "blocked_by": [1602]},
    {"issue": 1604, "feature": "Fd", "contract_touch": False, "priority": "low",
     "decision": "work", "issue_type": "enhancement", "blocked_by": [1602]},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"bug-outranks: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        # 1602 is a bug with fanout=2; 1601 is a high-priority enhancement with
        # fanout=0. The loop's score must rank the high-leverage bug ahead.
        if 1602 not in sel or 1601 not in sel:
            fail(f"bug-outranks: both items must appear, got {sel!r}")
        elif sel.index(1602) >= sel.index(1601):
            fail(f"bug-outranks: high-fanout bug #1602 must outrank "
                 f"enhancement #1601, got order {sel!r}")
        else:
            ok("bug-outranks: high-leverage bug at filer:medium outranks "
               "filer:high enhancement (filer label diluted)")
    except json.JSONDecodeError as e:
        fail(f"bug-outranks: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 17 — All signals equal → deterministic filer-label then issue#
#   When every observable signal is identical, ordering falls back to the
#   filer label, then issue number — fully deterministic (issue #441
#   acceptance).
# ---------------------------------------------------------------------------
items = [
    {"issue": 1703, "feature": "Fa", "contract_touch": False, "priority": "medium",
     "decision": "work", "issue_type": "enhancement", "blocked_by": []},
    {"issue": 1701, "feature": "Fb", "contract_touch": False, "priority": "high",
     "decision": "work", "issue_type": "enhancement", "blocked_by": []},
    {"issue": 1702, "feature": "Fc", "contract_touch": False, "priority": "high",
     "decision": "work", "issue_type": "enhancement", "blocked_by": []},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"equal-signals: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        # 1701, 1702 both high (filer label wins over 1703 medium); within the
        # high tier, issue# asc → 1701 before 1702; medium 1703 last.
        if sel != [1701, 1702, 1703]:
            fail(f"equal-signals: expected [1701, 1702, 1703] (filer label then "
                 f"issue#), got {sel!r}")
        else:
            ok("equal-signals: deterministic fallback to filer label then issue#")
    except json.JSONDecodeError as e:
        fail(f"equal-signals: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 18 — Computed score is transparent (issue #441)
#   Every emitted item carries both the filer label and the loop-computed
#   score so the loop's judgment is observable (the transparency
#   requirement). plan-batch emits a `computed_scores` map (issue-number
#   string → float in [0, 1]) alongside the existing keys.
# ---------------------------------------------------------------------------
items = [
    {"issue": 1801, "feature": "Fa", "contract_touch": False, "priority": "high",
     "decision": "work", "issue_type": "bug", "blocked_by": []},
    {"issue": 1802, "feature": "Fb", "contract_touch": False, "priority": "low",
     "decision": "work", "issue_type": "enhancement", "blocked_by": [1801]},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"transparency: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        scores = out.get("computed_scores")
        if not isinstance(scores, dict):
            fail(f"transparency: computed_scores must be a dict, got {scores!r}")
        elif set(scores.keys()) != {"1801", "1802"}:
            fail(f"transparency: computed_scores must cover every selected "
                 f"item, got keys {sorted(scores.keys())!r}")
        elif not all(isinstance(v, (int, float)) and 0.0 <= v <= 1.0
                     for v in scores.values()):
            fail(f"transparency: every score must be a float in [0,1], got "
                 f"{scores!r}")
        else:
            ok("transparency: computed_scores map present, normalized to [0,1], "
               "covers every selected item")
    except json.JSONDecodeError as e:
        fail(f"transparency: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 19 — Contract barrier still holds within a score tier (#441/#479)
#   #441 makes computed_score the PRIMARY ordering key but preserves the
#   contract-touch barrier as the SECONDARY tiebreak (Inv 26 grouping
#   correctness). Two items with identical computed signals, one
#   contract-touch: the contract item leads and lands in barrier_first.
# ---------------------------------------------------------------------------
items = [
    {"issue": 1901, "feature": "Fx", "contract_touch": False, "priority": "high",
     "decision": "work", "issue_type": "enhancement", "blocked_by": []},
    {"issue": 1902, "feature": "contract", "contract_touch": True, "priority": "high",
     "decision": "work", "issue_type": "enhancement", "blocked_by": []},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"score-tier-barrier: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        if out.get("barrier_first") != [1902]:
            fail(f"score-tier-barrier: contract item must lead within an equal "
                 f"score tier, barrier_first={out.get('barrier_first')!r}")
        elif out.get("selection_order") != [1902, 1901]:
            fail(f"score-tier-barrier: selection_order="
                 f"{out.get('selection_order')!r}, want [1902, 1901]")
        else:
            ok("score-tier-barrier: contract barrier preserved as secondary "
               "tiebreak within an equal score tier")
    except json.JSONDecodeError as e:
        fail(f"score-tier-barrier: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 20 — Full composite-key sweep across all priorities + contract +
#   issue numbers (issue #907). When every OTHER observable signal is held
#   equal (same scope size, no fanout, same issue_type, same created_at), the
#   filer label is the only differentiating score input, so ordering collapses
#   to the documented composite key:
#     (computed_score desc, contract_touch desc, issue asc).
#   With signals-equal-but-label, the label rank drives the score tiers
#   (critical > high > medium > low), contract_touch breaks ties WITHIN a tier
#   (contract leads), and issue# is the final stable tiebreak. This is the
#   single authoritative assertion the bug report asked for: the EXACT
#   selection_order over a queue mixing all priorities, contract/non-contract,
#   and various issue numbers — and barrier_first agreeing with it.
# ---------------------------------------------------------------------------
_COMMON = {"decision": "work", "issue_type": "enhancement",
           "created_at": "2026-05-01T00:00:00Z", "blocked_by": [],
           "features": ["F"]}
items = [
    # low tier (rank 3)
    {"issue": 2010, "feature": "Fa", "contract_touch": False, "priority": "low", **_COMMON},
    {"issue": 2009, "feature": "contract", "contract_touch": True, "priority": "low", **_COMMON},
    # medium tier (rank 2)
    {"issue": 2008, "feature": "Fb", "contract_touch": False, "priority": "medium", **_COMMON},
    {"issue": 2007, "feature": "contract", "contract_touch": True, "priority": "medium", **_COMMON},
    # high tier (rank 1)
    {"issue": 2006, "feature": "Fc", "contract_touch": False, "priority": "high", **_COMMON},
    # critical tier (rank 0) — two items to exercise the issue-asc tiebreak
    {"issue": 2005, "feature": "Fd", "contract_touch": False, "priority": "critical", **_COMMON},
    {"issue": 2001, "feature": "Fe", "contract_touch": False, "priority": "critical", **_COMMON},
    {"issue": 2002, "feature": "contract", "contract_touch": True, "priority": "critical", **_COMMON},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"composite-sweep: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        # critical tier: contract (2002) leads, then non-contract by issue asc
        #   (2001 before 2005); high (2006); medium: contract (2007) before
        #   non-contract (2008); low: contract (2009) before non-contract (2010).
        want = [2002, 2001, 2005, 2006, 2007, 2008, 2009, 2010]
        if sel != want:
            fail(f"composite-sweep: selection_order={sel!r}, want {want!r}")
        else:
            # barrier_first is the LEADING run of contract items: just [2002]
            # (the next item, 2001, is non-contract critical).
            bar = out.get("barrier_first", [])
            if bar != [2002]:
                fail(f"composite-sweep: barrier_first={bar!r}, want [2002]")
            elif sel[:len(bar)] != bar:
                fail(f"composite-sweep: barrier_first {bar!r} not a leading "
                     f"subsequence of selection_order {sel!r}")
            else:
                ok("composite-sweep: exact (computed_score desc, contract_touch "
                   "desc, issue asc) order; barrier_first agrees")
    except json.JSONDecodeError as e:
        fail(f"composite-sweep: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 21 — Medium leads low when all other signals are equal (#907 reg 1).
#   Queue {medium/contract, low/contract, low, low} with every other observable
#   signal held equal: the medium item MUST lead (its filer label gives it a
#   higher score tier than the low items). This is the #907 regression-1 shape;
#   it asserts the filer label still wins WHEN it is the only differing signal,
#   so a medium does not silently fall behind a low.
# ---------------------------------------------------------------------------
items = [
    {"issue": 898, "feature": "contract", "contract_touch": True, "priority": "medium", **_COMMON},
    {"issue": 894, "feature": "contract", "contract_touch": True, "priority": "low", **_COMMON},
    {"issue": 901, "feature": "rabbit-decompose", "contract_touch": False, "priority": "low", **_COMMON},
    {"issue": 889, "feature": "rabbit-cage", "contract_touch": False, "priority": "low", **_COMMON},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"medium-leads-low: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        # medium #898 first; then low tier: contract #894 before non-contract
        #   #889, #901 (issue asc).
        want = [898, 894, 889, 901]
        if sel != want:
            fail(f"medium-leads-low: selection_order={sel!r}, want {want!r} "
                 f"(#907 reg 1: medium must lead low at equal other signals)")
        elif sel[0] != 898:
            fail(f"medium-leads-low: medium #898 must lead, got {sel!r}")
        else:
            ok("medium-leads-low: medium item leads low items when other "
               "signals are equal (#907 reg 1)")
    except json.JSONDecodeError as e:
        fail(f"medium-leads-low: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario 22 — Issue-asc final tiebreak under a true score tie (#907 reg 2).
#   Queue {medium, medium, low} with all other signals equal: within the medium
#   tier (neither contract) the final tiebreak is issue ASC, so the lower issue
#   number leads. Locks the stable final tiebreak the bug report flagged.
# ---------------------------------------------------------------------------
items = [
    {"issue": 906, "feature": "Fa", "contract_touch": False, "priority": "medium", **_COMMON},
    {"issue": 902, "feature": "Fb", "contract_touch": False, "priority": "medium", **_COMMON},
    {"issue": 894, "feature": "Fc", "contract_touch": False, "priority": "low", **_COMMON},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"issue-asc-tiebreak: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        # medium tier: #902 before #906 (issue asc); low #894 last.
        want = [902, 906, 894]
        if sel != want:
            fail(f"issue-asc-tiebreak: selection_order={sel!r}, want {want!r} "
                 f"(#907 reg 2: issue-asc within an equal tier)")
        else:
            ok("issue-asc-tiebreak: lower issue# leads within a true score tie "
               "(#907 reg 2)")
    except json.JSONDecodeError as e:
        fail(f"issue-asc-tiebreak: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario — decomposition-parent exclusion (issue #948)
#   A work item carrying `decomposition_parent: true` (set upstream by
#   triage-issue.py from the native sub-issue rollup / the
#   decomposition_parents state map) is a recorded decomposition parent: it
#   carries no own code change and auto-closes via close-decomposed-parents.py
#   once its children close. plan-batch.py MUST filter it out of the
#   dispatchable plan (selection_order, dispatch_shapes, cross_scope_items)
#   while ordinary items remain selected and shaped.
# ---------------------------------------------------------------------------
items = [
    {"issue": 935, "feature": "feat-a", "contract_touch": False,
     "priority": "medium", "decomposition_parent": True, **_COMMON},
    {"issue": 950, "feature": "feat-b", "contract_touch": False,
     "priority": "medium", **_COMMON},
    {"issue": 942, "feature": "feat-c", "contract_touch": False,
     "priority": "medium", "decomposition_parent": False, **_COMMON},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"decomp-parent-exclude: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        shapes = out.get("dispatch_shapes", {})
        cross = out.get("cross_scope_items", [])
        if 935 in sel:
            fail(f"decomp-parent-exclude: parent 935 still in selection_order "
                 f"{sel!r} (#948)")
        elif "935" in shapes:
            fail("decomp-parent-exclude: parent 935 still in dispatch_shapes "
                 "(#948)")
        elif 935 in cross:
            fail("decomp-parent-exclude: parent 935 still in cross_scope_items "
                 "(#948)")
        elif 950 not in sel or 942 not in sel:
            fail(f"decomp-parent-exclude: non-parent item wrongly dropped; "
                 f"selection_order={sel!r} (#948)")
        elif shapes.get("950") != "parallel-per-feature":
            fail(f"decomp-parent-exclude: non-parent 950 shape="
                 f"{shapes.get('950')!r}, want parallel-per-feature (#948)")
        else:
            ok("decomp-parent-exclude: decomposition_parent item filtered from "
               "the plan; ordinary items still selected and shaped (#948)")
    except json.JSONDecodeError as e:
        fail(f"decomp-parent-exclude: bad JSON ({e}); stdout={proc.stdout!r}")


# ---------------------------------------------------------------------------
# Scenario — non-work / natively-blocked exclusion (issue #970, Inv 62)
#   plan-batch must surface ONLY dispatchable `work` items. A non-`work` triage
#   verdict (defer/blocked, close-not-planned/duplicate) MUST be absent from
#   ALL plan outputs (selection_order, dispatch_shapes, cross_scope_items),
#   mirroring the Inv 58 decomposition-parent filter. The genuine #970 leak:
#   triage-batch.py's defer-limit can FORCE a natively-blocked item to
#   `decision=work` (reason_code=defer-limit-reached) while it still carries an
#   OPEN `blocked_by` dependency (the authoritative blocked signal, Inv 59) —
#   such an item is NOT yet dispatchable and MUST also be excluded. A plain
#   `work` item and an ordinary cross_scope work item keep their existing
#   behaviour (no regression).
# ---------------------------------------------------------------------------
items = [
    # Plain work — selected and shaped normally.
    {"issue": 960, "feature": "feat-a", "features": ["feat-a"],
     "contract_touch": False, "priority": "high", "decision": "work",
     "blocked_by": []},
    # Natively blocked, deferred — must be absent.
    {"issue": 964, "feature": "feat-b", "features": ["feat-b"],
     "contract_touch": False, "priority": "high", "decision": "defer",
     "reason_code": "blocked", "blocked_by": [950]},
    # Duplicate close-not-planned — must be absent.
    {"issue": 965, "feature": "feat-c", "features": ["feat-c"],
     "contract_touch": False, "priority": "high",
     "decision": "close-not-planned", "reason_code": "duplicate",
     "blocked_by": []},
    # Force-promoted to work by the defer-limit, but STILL natively blocked
    # (open blocker in blocked_by) — the genuine #970 leak; must be absent.
    {"issue": 966, "feature": "feat-d", "features": ["feat-d"],
     "contract_touch": False, "priority": "high", "decision": "work",
     "reason_code": "defer-limit-reached", "blocked_by": [951]},
    # Cross-scope work item — still selected, shaped, and in cross_scope_items.
    {"issue": 967, "feature": "feat-e", "features": ["feat-e", "feat-f"],
     "contract_touch": False, "priority": "high", "decision": "work",
     "cross_scope": True, "blocked_by": []},
]
proc = run_plan(items)
if proc.returncode != 0:
    fail(f"non-work-exclude: exit {proc.returncode}; stderr={proc.stderr!r}")
else:
    try:
        out = json.loads(proc.stdout)
        sel = out.get("selection_order", [])
        shapes = out.get("dispatch_shapes", {})
        cross = out.get("cross_scope_items", [])
        # Deferred/blocked, duplicate, and force-promoted-but-blocked are gone.
        absent = [964, 965, 966]
        leaked = [n for n in absent
                  if n in sel or str(n) in shapes or n in cross]
        if leaked:
            fail(f"non-work-exclude: non-dispatchable items {leaked} leaked into "
                 f"the plan (selection_order={sel!r}, dispatch_shapes keys="
                 f"{sorted(shapes)!r}, cross_scope_items={cross!r}) (#970)")
        elif 960 not in sel:
            fail(f"non-work-exclude: plain work #960 must remain selected, "
                 f"got {sel!r} (#970)")
        elif shapes.get("960") != "parallel-per-feature":
            fail(f"non-work-exclude: work #960 shape={shapes.get('960')!r}, "
                 f"want parallel-per-feature (#970)")
        elif 967 not in sel:
            fail(f"non-work-exclude: cross_scope work #967 must remain "
                 f"selected, got {sel!r} (#970)")
        elif 967 not in cross:
            fail(f"non-work-exclude: cross_scope work #967 must remain in "
                 f"cross_scope_items, got {cross!r} (#970)")
        else:
            ok("non-work-exclude: defer/blocked, duplicate, and "
               "force-promoted-but-still-blocked items excluded from the plan; "
               "plain work + cross_scope work retained (#970)")
    except json.JSONDecodeError as e:
        fail(f"non-work-exclude: bad JSON ({e}); stdout={proc.stdout!r}")


sys.exit(FAIL)
