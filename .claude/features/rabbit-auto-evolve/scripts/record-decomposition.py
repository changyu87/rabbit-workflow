#!/usr/bin/env python3
"""record-decomposition.py — persist a decomposition parent->children linkage.

Usage:
  record-decomposition.py <parent#> <child#> [<child#> ...]

Per rabbit-auto-evolve spec.md Inv 53 (issue #721), when the dispatcher shapes
an item as `decomposition` (>= --decompose-threshold features) and files the N
per-feature child sub-issues, it MUST record the parent->children linkage in
MACHINE-READABLE form so the loop can deterministically enumerate a parent's
children (never from a prose comment table — the machine-first violation that
left #530 and #677 lingering OPEN after every child closed).

This script reads <state_dir>/auto-evolve-state.json, records the link under
the `decomposition_parents` map (parent-issue-number string -> sorted, deduped
list of child issue numbers), and writes the state back atomically. Recording
the same parent again UNIONS the new children with the existing list rather
than clobbering it; a new parent is additive.

  state_dir defaults to <cwd>/.rabbit
  state_dir is overridable via RABBIT_AUTO_EVOLVE_STATE_DIR (matching
  update-state.py / run-post-merge.py).

The written state's schema_version is left untouched (the caller's existing
state already carries schema 1.3.0, which defines `decomposition_parents`).
A missing state file is an error — decomposition only happens mid-tick, when
the loop already has a persisted state.

Exit code: 0 on a successful write; non-zero on a missing/malformed state
file, a bad argument, or a write error.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import sys


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def _state_path():
    return os.path.join(_state_dir(), "auto-evolve-state.json")


def _write_state(state):
    path = _state_path()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def run(parent, children):
    path = _state_path()
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, ValueError) as e:
        sys.stderr.write(
            f"record-decomposition: cannot read state {path}: {e}\n"
        )
        return 1

    dp = state.get("decomposition_parents")
    if not isinstance(dp, dict):
        dp = {}
    key = str(parent)
    existing = dp.get(key, [])
    if not isinstance(existing, list):
        existing = []
    merged = sorted({int(n) for n in existing} | set(children))
    dp[key] = merged
    state["decomposition_parents"] = dp

    _write_state(state)
    json.dump({"status": "recorded", "parent": parent, "children": merged},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Record a decomposition parent->children linkage under "
                    "the auto-evolve state's decomposition_parents map "
                    "(Inv 53 / #721). Unions with any existing children for "
                    "the parent; additive across parents."
    )
    parser.add_argument("parent", type=int, help="parent issue number")
    parser.add_argument("children", type=int, nargs="+",
                        help="one or more child sub-issue numbers")
    args = parser.parse_args()
    return run(args.parent, args.children)


if __name__ == "__main__":
    sys.exit(main())
