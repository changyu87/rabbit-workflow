#!/usr/bin/env python3
"""plan-batch.py — conflict-graph + barrier dispatch planner (Inv 4).

Reads a JSON array of triage objects on stdin (the caller passes only
items whose decision == "work") and emits a deterministic dispatch plan
on stdout:

  {
    "barrier_first": [123, 124],
    "groups": [[125, 126], [127]]
  }

Algorithm (per spec.md Inv 4 / design doc §6):
  1. Pull `contract_touch == true` items into barrier_first, sorted by
     priority desc (critical > high > medium > low; no-priority last)
     then issue ascending.
  2. Build a conflict graph on the remainder; an edge exists between A
     and B iff A.feature == B.feature.
  3. Greedy graph-color the remainder, walking in priority-desc /
     issue-asc order; each item takes the lowest color number with no
     same-feature neighbor.
  4. Apply --max-parallel cap (default 4): any color partition larger
     than the cap is split into consecutive sub-groups of size <= cap.

The script is a pure JSON processor — no gh, no git, no filesystem
mutations.

Exit code: 0 on success; non-zero on malformed stdin JSON or invalid
--max-parallel value.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import sys


PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_NO_PRIORITY_RANK = 4


def _sort_key(item):
    """(priority_rank, issue_number) — desc priority via low rank first;
    issue asc as tie-breaker."""
    rank = PRIORITY_RANK.get(item.get("priority", ""), _NO_PRIORITY_RANK)
    return (rank, item.get("issue", 0))


def _positive_int(value):
    """argparse type: integer >= 1."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"--max-parallel must be an integer, got {value!r}"
        )
    if n < 1:
        raise argparse.ArgumentTypeError(
            f"--max-parallel must be >= 1, got {n}"
        )
    return n


def plan(items, max_parallel):
    """Run the 4-step algorithm and return the plan dict."""
    # Drop items whose decision != "work" (per Inv 4 + Inv 18: plan-batch
    # accepts unfiltered triage arrays from triage-batch.py; only "work"
    # items are dispatched). Items without a `decision` field are passed
    # through (backwards-compat with pre-Inv-18 callers that pre-filter).
    items = [i for i in items if i.get("decision", "work") == "work"]

    # Step 1: barrier_first — all contract_touch items.
    barrier_items = sorted(
        [i for i in items if i.get("contract_touch")],
        key=_sort_key,
    )
    barrier_first = [i["issue"] for i in barrier_items]

    # Step 2/3: greedy graph color the remainder (edge iff same feature).
    remainder = sorted(
        [i for i in items if not i.get("contract_touch")],
        key=_sort_key,
    )
    color_features = []  # list[set[feature]] — index == color index
    color_items = []     # list[list[int]]   — index == color index

    for item in remainder:
        feat = item.get("feature")
        assigned = False
        for c in range(len(color_features)):
            if feat not in color_features[c]:
                color_features[c].add(feat)
                color_items[c].append(item["issue"])
                assigned = True
                break
        if not assigned:
            color_features.append({feat})
            color_items.append([item["issue"]])

    # Step 4: cap split — sub-groups of size <= max_parallel.
    groups = []
    for ci in color_items:
        for i in range(0, len(ci), max_parallel):
            groups.append(ci[i:i + max_parallel])

    return {"barrier_first": barrier_first, "groups": groups}


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic dispatch planner: reads triage JSON on "
                    "stdin, emits a barrier_first + groups plan on stdout. "
                    "Contract-touch issues are isolated; same-feature issues "
                    "never share a group; group size is capped by "
                    "--max-parallel."
    )
    parser.add_argument(
        "--max-parallel", type=_positive_int, default=4,
        help="Maximum group size (default: 4). Must be an integer >= 1.",
    )
    args = parser.parse_args()

    raw = sys.stdin.read()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"plan-batch: malformed stdin JSON: {e}\n")
        sys.exit(1)
    if not isinstance(items, list):
        sys.stderr.write(
            f"plan-batch: stdin must be a JSON array, got "
            f"{type(items).__name__}\n"
        )
        sys.exit(1)

    result = plan(items, args.max_parallel)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
