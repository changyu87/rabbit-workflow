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

Exit code: 0 on success (including with per-issue failures handled as
defer entries); non-zero on malformed stdin JSON.

The triage-issue.py path resolves via the env override
`RABBIT_AUTO_EVOLVE_SCRIPT_DIR` (test seam) else the sibling script
directory of this file.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys


def _resolve_triage_issue_path():
    """Default to sibling script; allow RABBIT_AUTO_EVOLVE_SCRIPT_DIR override."""
    override = os.environ.get("RABBIT_AUTO_EVOLVE_SCRIPT_DIR")
    base = override if override else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "triage-issue.py")


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
    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
