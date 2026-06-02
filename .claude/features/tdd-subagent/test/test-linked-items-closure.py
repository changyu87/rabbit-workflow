#!/usr/bin/env python3
"""Inv 19, 20, 21 — primary linked-item closure, secondary linked-items
closure, HANDOFF lists all closed items."""
import json
import re

from _helpers import run_dispatch, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


def render_prompt(*extra):
    res = run_dispatch(*extra)
    if res.returncode != 0:
        ko(f"dispatch failed rc={res.returncode}: {res.stderr}")
        raise SystemExit(1)
    return res.stdout


# Baseline: no items → no close-call block and empty closed_items in JSON.
baseline = render_prompt()
if "IMPL_SHA=$(git rev-parse HEAD)" not in re.findall(
    r"After the test-green transition is committed,.*?IMPL_SHA=\$\(git rev-parse HEAD\)",
    baseline, re.DOTALL,
) and "After the test-green transition" not in baseline:
    ok("inv21: baseline (no items) — no close-call block in UNLOCK")
else:
    ko("inv21: baseline emits close-call block when no items present")
m = re.search(r'"closed_items":\s*(\[[^\]]*\])', baseline)
if m and m.group(1) == "[]":
    ok("inv21: baseline HANDOFF_JSON closed_items is []")
else:
    ko(f"inv21: baseline HANDOFF_JSON closed_items not [] (got {m.group(1) if m else 'missing'})")

# Inv 19: primary --linked-item triggers item-status.py set close.
primary = render_prompt(
    "--linked-item", "rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-1",
    "--item-type", "bug",
)
expected_primary = re.search(
    r"item-status\.py set \\\n"
    r"\s*--feature rabbit-cage --type bug --id RABBIT-CAGE-BUG-1 \\\n"
    r"\s*--status close \\\n"
    r"\s*--reason 'TDD cycle complete' \\\n"
    r"\s*--fix-commits \$IMPL_SHA",
    primary,
)
if expected_primary:
    ok("inv19: primary close call uses item-status.py with derived feature/id and primary reason")
else:
    ko("inv19: primary close call missing or malformed")

# Inv 21: HANDOFF lists primary.
if "(primary, type=bug)" in primary:
    ok("inv21: HANDOFF YAML lists primary item")
else:
    ko("inv21: HANDOFF YAML missing primary item")
m = re.search(r'"closed_items":\s*\[\s*([^\]]+)\s*\]', primary)
if m and "RABBIT-CAGE-BUG-1" in m.group(1):
    ok("inv21: HANDOFF_JSON closed_items lists primary")
else:
    ko("inv21: HANDOFF_JSON closed_items missing primary")

# Inv 20: secondary --linked-items entries trigger additional close calls.
combined = render_prompt(
    "--linked-item", "rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-1",
    "--item-type", "bug",
    "--linked-items", "rabbit-config:bug:RABBIT-CONFIG-BUG-2,tdd-subagent:backlog:TDD-SUBAGENT-BACKLOG-3",
)
secondary_call = re.search(
    r"item-status\.py set \\\n"
    r"\s*--feature rabbit-config --type bug --id RABBIT-CONFIG-BUG-2 \\\n"
    r"\s*--status close \\\n"
    r"\s*--reason 'TDD cycle complete \(secondary item resolved by same commit\)' \\\n"
    r"\s*--fix-commits \$IMPL_SHA",
    combined,
)
if secondary_call:
    ok("inv20: secondary close call uses secondary reason")
else:
    ko("inv20: secondary close call missing or malformed")
if "TDD-SUBAGENT-BACKLOG-3" in combined and "tdd-subagent" in combined:
    ok("inv20: second secondary item also rendered")
else:
    ko("inv20: second secondary item not rendered")

# Inv 21: HANDOFF_JSON lists all three items.
m = re.search(r'"closed_items":\s*\[(.*?)\]', combined, re.DOTALL)
if m and all(
    s in m.group(1) for s in ("RABBIT-CAGE-BUG-1", "RABBIT-CONFIG-BUG-2", "TDD-SUBAGENT-BACKLOG-3")
):
    ok("inv21: HANDOFF_JSON closed_items lists primary + both secondaries")
else:
    ko(f"inv21: HANDOFF_JSON closed_items incomplete: {m.group(1) if m else 'missing'}")

report(passed, failed)
