#!/usr/bin/env python3
"""Script-backed-orchestration cleanliness for rabbit-issue (issue #874).

Runs the rabbit-housekeep script-backed scanner against the rabbit-issue
feature tree and asserts it reports zero findings. A finding means a fenced
bash block in a SKILL.md carries a runtime placeholder, mode-aware branch, or
computed value that the model would assemble at invocation time — a prompt-tier
step that spec-rules §4 (Script-Backed Orchestration) forbids.

Illustrative CLI synopses (documenting how to invoke a companion script) are
exempt only when annotated with the `<!-- example -->` marker on the line
directly above the opening fence, the mechanism shipped in #869. This test
keeps the feature at a clean baseline so a future SKILL edit that introduces a
real (unmarked) orchestration placeholder fails loudly.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the script-backed scanner is folded into the
    cross-feature contract gate and per-feature assertions become redundant.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = FEATURE_DIR.parents[2]
SCANNER = (
    REPO_ROOT
    / ".claude"
    / "features"
    / "rabbit-housekeep"
    / "scripts"
    / "check-script-backed.py"
)


def main() -> int:
    if not SCANNER.is_file():
        print(f"FAIL: scanner not found at {SCANNER}", file=sys.stderr)
        return 1

    result = subprocess.run(
        [sys.executable, str(SCANNER), "scan", str(FEATURE_DIR)],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        print(
            f"FAIL: scanner errored (rc={result.returncode}): {result.stderr}",
            file=sys.stderr,
        )
        return 1

    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(
            f"FAIL: scanner output not JSON: {exc}\n{result.stdout}",
            file=sys.stderr,
        )
        return 1

    count = report.get("count")
    if count != 0:
        print(
            f"FAIL: scanner reports {count} script-backed finding(s):",
            file=sys.stderr,
        )
        for finding in report.get("findings", []):
            print(f"  - {finding}", file=sys.stderr)
        return 1

    print("PASS test-script-backed-clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
