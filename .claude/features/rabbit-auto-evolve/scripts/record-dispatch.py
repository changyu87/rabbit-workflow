#!/usr/bin/env python3
"""record-dispatch.py — the script-owned dispatch-journal WRITE point (Inv 54).

Usage:
  record-dispatch.py --tick-id <id> --issue <N> --feature <name>
                     --shape <shape> [--status <status>]
                     [--branch <b>] [--worktree <w>] [--pr <N>]

Per rabbit-auto-evolve spec.md Inv 54, performs an atomic read-modify-write of
the per-tick dispatch journal in <state_dir>/auto-evolve-state.json:

  - locates (or creates) the tick bucket keyed by <tick-id>, seeding
    `started_at` once per tick on first write;
  - finds the entry for <issue> under that tick and UPDATES it in place when
    present (a repeated call for the same (tick-id, issue) NEVER duplicates),
    or APPENDS a new entry otherwise;
  - sets the supplied fields (issue/feature/shape/status always; branch/
    worktree/pr when supplied — an omitted optional leaves the prior value).

The dispatcher invokes this at Phase 6: once per Agent call at dispatch time
(`--status dispatched`) and once when each HANDOFF returns (`--status pr_open`
/`aborted`, recording `--branch`/`--pr`). The journal write is SCRIPT-OWNED so
the SKILL.md Phase 6 body carries no computed-value bash (Script-Backed
Orchestration, spec-rules §1: script > prompt).

State dir resolves via RABBIT_AUTO_EVOLVE_STATE_DIR when set, else
<cwd>/.rabbit (matching update-state.py). The write is atomic via temp+rename.
A missing/malformed state file is a LOUD error (exit non-zero, nothing
written) — the dispatcher must see a locatable failure, never a silent drop.

The written entry is emitted as JSON on stdout. Exit 0 on success; non-zero
on a missing/malformed state file or invalid args.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import datetime
import json
import os
import sys

_STATUSES = {"dispatched", "pr_open", "completed", "aborted"}


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _state_path():
    return os.path.join(_state_dir(), "auto-evolve-state.json")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _write_state(state):
    path = _state_path()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def record(args):
    path = _state_path()
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, ValueError) as e:
        sys.stderr.write(
            f"record-dispatch: cannot read state file {path}: {e}\n")
        return 1
    if not isinstance(state, dict):
        sys.stderr.write(
            f"record-dispatch: state file {path} is not a JSON object\n")
        return 1

    journal = state.setdefault("dispatch_journal", {})
    if not isinstance(journal, dict):
        sys.stderr.write(
            "record-dispatch: dispatch_journal is not an object\n")
        return 1

    tick = journal.get(args.tick_id)
    if tick is None or not isinstance(tick, dict):
        tick = {"started_at": _now_iso(), "entries": []}
        journal[args.tick_id] = tick
    tick.setdefault("started_at", _now_iso())
    entries = tick.setdefault("entries", [])

    # Find an existing entry for this issue (UPDATE in place — never duplicate).
    entry = None
    for e in entries:
        if isinstance(e, dict) and e.get("issue") == args.issue:
            entry = e
            break
    if entry is None:
        entry = {"issue": args.issue, "feature": args.feature,
                 "shape": args.shape, "branch": None, "worktree": None,
                 "pr": None, "status": args.status}
        entries.append(entry)
    else:
        entry["feature"] = args.feature
        entry["shape"] = args.shape
        entry["status"] = args.status

    if args.branch is not None:
        entry["branch"] = args.branch
    if args.worktree is not None:
        entry["worktree"] = args.worktree
    if args.pr is not None:
        entry["pr"] = args.pr

    state["updated_at"] = _now_iso()
    _write_state(state)

    json.dump(entry, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Record (append or update-in-place) a per-tick dispatch "
                    "journal entry in .rabbit/auto-evolve-state.json (Inv 54). "
                    "Honors RABBIT_AUTO_EVOLVE_STATE_DIR.")
    parser.add_argument("--tick-id", required=True,
                        help="the tick id keying the journal bucket")
    parser.add_argument("--issue", required=True, type=int,
                        help="the dispatched issue number")
    parser.add_argument("--feature", required=True,
                        help="the issue's feature")
    parser.add_argument("--shape", required=True,
                        help="the dispatch shape (e.g. parallel-per-feature)")
    parser.add_argument("--status", default="dispatched", choices=sorted(_STATUSES),
                        help="entry status (default: dispatched)")
    parser.add_argument("--branch", default=None,
                        help="the dispatched branch (optional)")
    parser.add_argument("--worktree", default=None,
                        help="the dispatch worktree path (optional)")
    parser.add_argument("--pr", default=None, type=int,
                        help="the returned PR number (optional)")
    args = parser.parse_args()
    return record(args)


if __name__ == "__main__":
    sys.exit(main())
