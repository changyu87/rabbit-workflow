#!/usr/bin/env python3
"""status-report.py — deterministic backing script for the `status` subcommand.

Per rabbit-auto-evolve spec.md Inv 29 (added v0.17.0 for issue #405), this
CLI is the read-only backing for `/rabbit-auto-evolve status`. It replaces
the prior LLM-assembled `ls`/`cat`/`jq` bash pipeline (a non-deterministic,
untestable surface that drifted and emitted ugly `ls: cannot access ...` stderr
noise on a fresh clone where the state file and markers do not yet exist).
Per spec-rules §1 (`script > CLI > spec > prompt`) the surface is a script.

It reads ONLY:
  - <repo_root>/.rabbit/auto-evolve-state.json for the five state fields.
    When the file is MISSING, empty, or fails JSON parse, defaults are emitted
    (a missing state file is the legitimate fresh-clone case, NOT an error).
  - The five runtime markers via os.path.exists.

It performs NO mutations, NO `gh`, and NO `git` shellouts.

It emits a single fixed-format JSON object on stdout:

  {
    "queue_length": <int>,
    "in_flight": [<int>, ...],
    "last_merged_sha": <str|null>,
    "last_tagged_version": <str|null>,
    "consecutive_failures": <int>,
    "markers_present": [<sorted marker basenames>],
    "state_file": "present" | "absent" | "malformed"
  }

Exit code is 0 on success (including every defaults path). A non-zero exit
is reserved for genuine invocation errors. The verdict lives in the JSON,
never in the exit code.

<repo_root> defaults to os.getcwd(); overridable via the
RABBIT_AUTO_EVOLVE_REPO_ROOT env var for tests (matching
check-preconditions.py and banner-status.py).

Issue #838 (Inv 54): `in_flight` is DERIVED as a read-only projection of the
`dispatch_journal` (the union of dispatched/pr_open issue numbers), falling
back to a literal `in_flight` array when no journal is present.

Version: 1.1.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

STATE_PATH = os.path.join(".rabbit", "auto-evolve-state.json")

MARKERS = [
    ".rabbit-auto-evolve-active",
    ".rabbit-auto-evolve-running",
    ".rabbit-auto-evolve-stop-requested",
    ".rabbit-auto-evolve-restart-needed",
    ".rabbit-auto-evolve-aborted",
]


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _read_state(repo_root: str) -> tuple[dict, str]:
    """Return (state_dict, status) where status is present|absent|malformed.

    On absent or malformed, the returned dict is empty {} and the caller
    falls back to per-field defaults.
    """
    path = os.path.join(repo_root, STATE_PATH)
    if not os.path.exists(path):
        return {}, "absent"
    try:
        with open(path) as f:
            text = f.read()
    except OSError:
        return {}, "malformed"
    if not text.strip():
        return {}, "malformed"
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}, "malformed"
    if not isinstance(data, dict):
        return {}, "malformed"
    return data, "present"


def _markers_present(repo_root: str) -> list[str]:
    return sorted(
        name for name in MARKERS if os.path.exists(os.path.join(repo_root, name))
    )


def _derive_in_flight(state: dict) -> list:
    """The in-flight issue set (Inv 54). DERIVED as a read-only projection of
    the dispatch_journal — the sorted union of issue numbers whose journal
    status is `dispatched` or `pr_open` (NOT completed/aborted) across every
    tracked tick. Falls back to the literal `in_flight` array when no journal
    is present, so the surface is unchanged for consumers after `in_flight`
    was retired as a required field."""
    journal = state.get("dispatch_journal")
    if isinstance(journal, dict) and journal:
        live = {"dispatched", "pr_open"}
        issues = set()
        for tick in journal.values():
            if not isinstance(tick, dict):
                continue
            for e in tick.get("entries", []):
                if not isinstance(e, dict):
                    continue
                issue = e.get("issue")
                if e.get("status") in live and isinstance(issue, int) \
                        and not isinstance(issue, bool):
                    issues.add(issue)
        return sorted(issues)
    literal = state.get("in_flight")
    if isinstance(literal, list):
        return literal
    return []


def build_report(repo_root: str) -> dict:
    state, state_file = _read_state(repo_root)

    queue = state.get("queue")
    queue_length = len(queue) if isinstance(queue, list) else 0

    in_flight = _derive_in_flight(state)

    last_merged_sha = state.get("last_merged_sha")
    if not isinstance(last_merged_sha, str):
        last_merged_sha = None

    last_tagged_version = state.get("last_tagged_version")
    if not isinstance(last_tagged_version, str):
        last_tagged_version = None

    consecutive_failures = state.get("consecutive_failures")
    if not isinstance(consecutive_failures, int) or isinstance(
        consecutive_failures, bool
    ):
        consecutive_failures = 0

    return {
        "queue_length": queue_length,
        "in_flight": in_flight,
        "last_merged_sha": last_merged_sha,
        "last_tagged_version": last_tagged_version,
        "consecutive_failures": consecutive_failures,
        "markers_present": _markers_present(repo_root),
        "state_file": state_file,
    }


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "Read-only rabbit-auto-evolve status: inspect "
            ".rabbit/auto-evolve-state.json (defaults on missing/malformed) and "
            "the five runtime markers, and emit a fixed-format status JSON. "
            "Exit code is always 0 except on a genuine invocation error."
        )
    ).parse_args()

    report = build_report(_repo_root())
    print(json.dumps(report, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
