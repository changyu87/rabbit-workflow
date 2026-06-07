#!/usr/bin/env python3
"""resume-dispatch.py — the script-owned dispatch-journal READ/RESUME point (Inv 54).

Usage:
  cat plan.json | resume-dispatch.py --tick-id <id>

Per rabbit-auto-evolve spec.md Inv 54, reads a plan JSON on stdin (carrying
`selection_order`, the planned dispatch order) and the active tick's dispatch
journal from <state_dir>/auto-evolve-state.json, and partitions the planned
issues into a `dispatch` set (re-enter Phase 6) and a `skip` set (already
handled this cycle):

  - journal status `completed` -> SKIP (its PR merged; nothing to do).
  - journal status `pr_open`   -> SKIP (the open PR drains through the normal
    merge path, Phase 7 — never a second dispatch).
  - journal status `dispatched` with NO recorded PR -> RE-dispatch (the prior
    dispatch was interrupted before producing a PR).
  - journal status `aborted` -> RE-dispatch (a future tick may retry).
  - issue ABSENT from the journal -> dispatch normally (never seen this cycle).

A missing/empty/absent journal yields every planned issue in `dispatch` —
today's behavior (re-fetch each tick), the no-regression base.

Emits `{"dispatch": [...], "skip": [...]}` on stdout, each list preserving the
input `selection_order`. State dir resolves via RABBIT_AUTO_EVOLVE_STATE_DIR
when set, else <cwd>/.rabbit (matching update-state.py). Reads only; no
mutation.

Exit 0 on success; non-zero on malformed stdin JSON.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import sys

# Statuses whose journal entry means the issue is already handled THIS cycle
# and must NOT be re-dispatched. `dispatched` (no PR) and `aborted` fall
# through to RE-dispatch.
_SKIP_STATUSES = {"completed", "pr_open"}


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _state_path():
    return os.path.join(_state_dir(), "auto-evolve-state.json")


def _journal_status_by_issue(tick_id):
    """Return {issue: status} for the given tick's journal entries. Empty dict
    when the state file / journal / tick is missing or malformed (no-regression
    base: every planned issue then dispatches)."""
    try:
        with open(_state_path()) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(state, dict):
        return {}
    journal = state.get("dispatch_journal")
    if not isinstance(journal, dict):
        return {}
    tick = journal.get(tick_id)
    if not isinstance(tick, dict):
        return {}
    entries = tick.get("entries")
    if not isinstance(entries, list):
        return {}
    out = {}
    for e in entries:
        if isinstance(e, dict) and isinstance(e.get("issue"), int) \
                and not isinstance(e.get("issue"), bool):
            out[e["issue"]] = e.get("status")
    return out


def partition(selection_order, status_by_issue):
    """Partition selection_order into (dispatch, skip), preserving order. An
    issue is SKIPPED iff its journal status is in _SKIP_STATUSES; every other
    case (dispatched-no-PR, aborted, absent) re-dispatches."""
    dispatch, skip = [], []
    for issue in selection_order:
        status = status_by_issue.get(issue)
        if status in _SKIP_STATUSES:
            skip.append(issue)
        else:
            dispatch.append(issue)
    return dispatch, skip


def main():
    parser = argparse.ArgumentParser(
        description="Partition a plan's selection_order (stdin) into dispatch "
                    "and skip sets by consulting the active tick's dispatch "
                    "journal (Inv 54). Honors RABBIT_AUTO_EVOLVE_STATE_DIR.")
    parser.add_argument("--tick-id", required=True,
                        help="the tick id keying the journal bucket")
    args = parser.parse_args()

    raw = sys.stdin.read()
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"resume-dispatch: stdin is not valid JSON: {e}\n")
        return 1
    if not isinstance(plan, dict):
        sys.stderr.write("resume-dispatch: stdin plan must be a JSON object\n")
        return 1
    selection_order = plan.get("selection_order")
    if not isinstance(selection_order, list):
        selection_order = []

    status_by_issue = _journal_status_by_issue(args.tick_id)
    dispatch, skip = partition(selection_order, status_by_issue)

    json.dump({"dispatch": dispatch, "skip": skip}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
