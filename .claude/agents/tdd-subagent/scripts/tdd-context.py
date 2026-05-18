#!/usr/bin/env python3
# tdd-context.py — emit machine-first JSON describing a feature's TDD state,
# intended for inclusion in subagent prompts so every spawned agent knows:
#   - which feature it is working on
#   - what TDD step it is in
#   - what the next allowed step is (and what triggers it)
#   - the deprecation criterion (so it doesn't accidentally extend EOL'd code)
#   - the contract (what it reads / writes / invokes)
#
# Usage:
#   tdd-context.py <feature-dir>          # JSON output (default)
#   tdd-context.py --text <feature-dir>   # human-readable summary
#
# Exit:
#   0 success
#   2 invocation error

import json
import os
import sys


_ALLOWED_NEXT = {
    "spec":        ["spec-update"],
    "spec-update": ["test-red"],
    "test-red":    ["impl"],
    "impl":        ["test-green"],
    "test-green":  ["deprecated"],
    "deprecated":  [],
}


def allowed_next(state):
    return _ALLOWED_NEXT.get(state, [])


def guidance_for(state):
    if state == "spec":
        return ("Author end-to-end tests under test/. They MUST be runnable unattended (no human input). "
                "They MUST fail (red) when run, since no implementation exists yet. "
                "Then transition to spec-update.")
    if state == "spec-update":
        return ("Update docs/spec/spec.md to describe the planned change. "
                "A git diff showing spec edits must be present before transitioning to test-red "
                "(or provide --spec-no-change-reason). Then transition to test-red.")
    if state == "test-red":
        return ("Tests exist and fail. Begin implementation under scripts/ (or wherever the spec dictates). "
                "Do NOT modify the tests to make them pass. "
                "Then transition to impl when implementation work has started.")
    if state == "impl":
        return ("Implementation in progress. Run test/run.py frequently. "
                "When all tests pass, transition to test-green.")
    if state == "test-green":
        return ("All tests pass. Open a pull request now (branch should already exist per branch-per-feature). "
                "The PR/merge process handles review and merge; "
                "transition to deprecated when superseded per the deprecation criterion.")
    if state == "deprecated":
        return ("TERMINAL. Do not extend or modify behavior. "
                "Direct callers to the successor (if any). "
                "This feature should be removed when the deprecation criterion is fully met.")
    return "Unknown state. Repair feature.json before proceeding."


def build_json(feat_data, name, state, crit):
    return {
        "feature_name": name,
        "current_state": state,
        "allowed_next_states": allowed_next(state),
        "guidance": guidance_for(state),
        "deprecation_criterion": crit,
        "contract": feat_data.get("contract"),
        "version": feat_data.get("version"),
        "owner": feat_data.get("owner"),
        "status": feat_data.get("status"),
    }


def main(argv):
    mode = "json"
    if argv and argv[0] == "--text":
        mode = "text"
        argv = argv[1:]

    if not argv:
        sys.stderr.write("usage: tdd-context.py [--text] <feature-dir>\n")
        return 2
    d = argv[0]
    feat_path = os.path.join(d, "feature.json")
    if not os.path.isfile(feat_path):
        sys.stderr.write(f"ERROR: no feature.json in {d}\n")
        return 2

    try:
        with open(feat_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"ERROR: failed to parse {feat_path}: {e}\n")
        return 2

    state = data.get("tdd_state", "") or ""
    name = data.get("name", "") or ""
    # Inv 28: prefer flat `deprecation_criterion` (canonical); fall back to
    # legacy nested `deprecation.criterion` when flat is absent.
    crit = data.get("deprecation_criterion") or ""
    if not crit:
        deprecation = data.get("deprecation") or {}
        if isinstance(deprecation, dict):
            crit = deprecation.get("criterion", "") or ""

    if mode == "json":
        out = build_json(data, name, state, crit)
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    # Text mode
    nxt = ", ".join(allowed_next(state))
    sys.stdout.write(
        f"Feature: {name}\n"
        f"Current state: {state}\n"
        f"Next allowed state(s): {nxt}\n"
        f"Guidance:\n  {guidance_for(state)}\n"
        f"Deprecation criterion:\n  {crit}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
