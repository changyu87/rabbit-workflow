#!/usr/bin/env python3
"""triage-batch.py — bridge fetch-queue → plan-batch (Inv 18).

Reads a JSON array on stdin (the raw `gh issue list` shape emitted by
`fetch-queue.py`: `[{number, title, labels, body, createdAt}, ...]`),
invokes `triage-issue.py <number>` once per item, concatenates the
per-issue triage JSON objects into a single array in input order, and
emits that array on stdout.

Per-issue failure handling: if any per-issue `triage-issue.py` invocation
exits non-zero, the failed issue's slot is filled with a synthesized
triage object

    {"issue": N, "decision": "defer", "reason_code": "triage-failed",
     "rationale": "<stderr snippet>", "feature": null,
     "contract_touch": false, "blocked_by": []}

and the batch CONTINUES processing remaining issues. The script never
aborts mid-batch on a single-issue failure — graceful degradation matters
for tick liveness.

Anti-infinite-defer (issue #423 Part B): triage-batch.py owns a per-issue
consecutive-defer counter persisted in `.rabbit/auto-evolve-state.json`
under the `defer_counts` map (keyed by issue-number string). For each
triaged issue:
  - a `defer` decision increments the issue's counter; if the counter was
    already >= 3 (i.e. this would be the 4th consecutive defer), the
    decision is FORCED to `work` with reason_code `defer-limit-reached`
    and the accumulated planning-note history is surfaced — dispatch is
    mandatory after 3 consecutive deferrals.
  - any non-defer decision RESETS the issue's counter to 0 (the counter
    tracks CONSECUTIVE defers, not lifetime).
The updated `defer_counts` map is written back to the state file via an
atomic temp+rename (read-modify-write, preserving all other state keys).
Persistence is best-effort: if no state file exists or it fails to parse,
counts default to empty and the decisions pass through unchanged — tick
liveness must never depend on the state file already existing. The state
dir resolves via `RABBIT_AUTO_EVOLVE_STATE_DIR` (test seam, matching
update-state.py) else `<cwd>/.rabbit`.

Exit code: 0 on success (including with per-issue failures handled as
defer entries); non-zero on malformed stdin JSON.

The triage-issue.py path resolves via the env override
`RABBIT_AUTO_EVOLVE_SCRIPT_DIR` (test seam) else the sibling script
directory of this file.

Version: 1.1.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys


# After this many CONSECUTIVE defers on the same issue, the next tick forces
# `work` (dispatch becomes mandatory). 3 defers → the 4th is forced.
DEFER_LIMIT = 3


def _resolve_triage_issue_path():
    """Default to sibling script; allow RABBIT_AUTO_EVOLVE_SCRIPT_DIR override."""
    override = os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR")
    base = override if override else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "triage-issue.py")


def _resolve_state_path():
    """Path to .rabbit/auto-evolve-state.json. Honors the
    RABBIT_AUTO_EVOLVE_STATE_DIR override (matching update-state.py)."""
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    state_dir = override if override else os.path.join(os.getcwd(), ".rabbit")
    return os.path.join(state_dir, "auto-evolve-state.json")


def _load_state(state_path):
    """Return the parsed state dict, or None if the file is absent / empty /
    unparseable (best-effort — never raises)."""
    try:
        with open(state_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _persist_state(state_path, state):
    """Atomically write `state` back via temp+rename (preserving every key).
    Best-effort: any OSError is swallowed so persistence never breaks the
    batch output (tick liveness)."""
    tmp_path = state_path + ".tmp"
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.rename(tmp_path, state_path)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _apply_defer_counter(results, defer_counts):
    """Mutate `results` in place applying the anti-infinite-defer rule and
    return the updated `defer_counts` map (keyed by issue-number string).

    For each result:
      - decision == "defer" and prior count >= DEFER_LIMIT → FORCE "work"
        (reason_code "defer-limit-reached"); reset the counter to 0 since
        the issue is now being dispatched.
      - decision == "defer" otherwise → increment the counter.
      - any non-defer decision → reset the counter to 0.
    """
    counts = dict(defer_counts)
    for r in results:
        issue = r.get("issue")
        if issue is None:
            continue
        key = str(issue)
        prior = counts.get(key, 0)
        if r.get("decision") == "defer":
            if prior >= DEFER_LIMIT:
                prior_note = r.get("planning_note")
                forced_note = (
                    f"Forced to work after {prior} consecutive deferrals "
                    f"(limit {DEFER_LIMIT}); dispatch is now mandatory."
                )
                if prior_note:
                    forced_note += f" Prior planning note: {prior_note}"
                r["decision"] = "work"
                r["reason_code"] = "defer-limit-reached"
                r["planning_note"] = forced_note
                counts[key] = 0
            else:
                counts[key] = prior + 1
        else:
            counts[key] = 0
    return counts


def _defer_entry(issue_num, stderr):
    snippet = (stderr or "").strip()[:200] or "triage-issue exited non-zero"
    return {
        "issue": issue_num,
        "decision": "defer",
        "reason_code": "triage-failed",
        "rationale": snippet,
        "feature": None,
        "contract_touch": False,
        "blocked_by": [],
        "planning_note": "Re-run triage for this issue; the per-issue "
                         "classifier exited non-zero this tick.",
    }


def batch(items, triage_issue_path):
    """Run triage-issue.py per input item; return the concatenated array."""
    results = []
    for item in items:
        num = item.get("number")
        proc = subprocess.run(
            [sys.executable, triage_issue_path, str(num)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode == 0:
            try:
                results.append(json.loads(proc.stdout))
            except json.JSONDecodeError as e:
                results.append(_defer_entry(num, f"malformed triage stdout: {e}"))
        else:
            results.append(_defer_entry(num, proc.stderr))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Bridge fetch-queue raw issue list to plan-batch's "
                    "triage-object input shape: invokes triage-issue.py per "
                    "issue and concatenates results. Per-issue failures "
                    "become defer/triage-failed entries; batch continues. "
                    "Usage: cat fetch-queue.json | triage-batch.py"
    )
    parser.parse_args()

    raw = sys.stdin.read()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"triage-batch: malformed stdin JSON: {e}\n")
        sys.exit(1)
    if not isinstance(items, list):
        sys.stderr.write(
            f"triage-batch: stdin must be a JSON array, got "
            f"{type(items).__name__}\n"
        )
        sys.exit(1)

    triage_issue_path = _resolve_triage_issue_path()
    results = batch(items, triage_issue_path)

    # Anti-infinite-defer (issue #423 Part B): apply the consecutive-defer
    # counter, forcing `work` on the 4th consecutive defer. Persistence is
    # best-effort — if there is no state file, decisions still pass through.
    state_path = _resolve_state_path()
    state = _load_state(state_path)
    if state is not None:
        defer_counts = state.get("defer_counts", {})
        if not isinstance(defer_counts, dict):
            defer_counts = {}
        state["defer_counts"] = _apply_defer_counter(results, defer_counts)
        _persist_state(state_path, state)
    else:
        # No usable state file — apply forcing against an empty counter so
        # current-tick behavior is consistent, but skip persistence.
        _apply_defer_counter(results, {})

    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
