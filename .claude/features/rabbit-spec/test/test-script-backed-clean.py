#!/usr/bin/env python3
"""#875 (child of #863): rabbit-spec carries zero script-backed-orchestration
findings (Inv 8, spec-rules §4 Script-Backed Orchestration).

End-to-end guard: runs the canonical scanner
`.claude/features/rabbit-housekeep/scripts/check-script-backed.py scan` against
the rabbit-spec feature dir and asserts it reports `count: 0`. Post-#922 the
rabbit-spec-create skill (whose Step 1 once carried the only historical
finding) is retired; the surviving authored bodies (the rabbit-spec-update
SKILL.md and the rabbit-spec-creator agent) carry no unmarked
runtime-placeholder fenced blocks. This test keeps the feature clean: a future
unmarked runtime-placeholder / computed-value / mode-aware-branching step
re-flags and fails here.

Static check; no runtime behaviour.

Version: 2.0.0
Owner: rabbit-workflow team
Deprecation criterion: when script-backed-orchestration linting is provided
    natively by the rabbit CLI as a housekeeping subcommand
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# repo root: .claude/features/rabbit-spec/test -> parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]
SCANNER = (
    REPO_ROOT
    / ".claude" / "features" / "rabbit-housekeep" / "scripts"
    / "check-script-backed.py"
)


def test_scanner_reports_zero_findings() -> None:
    assert SCANNER.is_file(), f"missing scanner: {SCANNER}"
    proc = subprocess.run(
        [sys.executable, str(SCANNER), "scan", str(FEATURE_DIR)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"scanner exited {proc.returncode}: {proc.stderr}"
    )
    report = json.loads(proc.stdout)
    assert report["count"] == 0, (
        "rabbit-spec must carry zero script-backed-orchestration findings "
        f"(Inv 9, #875). Scanner reported {report['count']}:\n"
        + json.dumps(report["findings"], indent=2)
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            fail += 1
    sys.exit(0 if fail == 0 else 1)
