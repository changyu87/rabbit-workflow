#!/usr/bin/env python3
"""mark-aborted.py — write the .rabbit-auto-evolve-aborted marker with a
reason string.

Usage:
  mark-aborted.py <reason>

Per rabbit-auto-evolve spec.md Inv 17, all rabbit-auto-evolve runtime-marker
writes go through scripts so scope-guard (which inspects literal Bash command
strings) does not block them. This script wraps the tick's abort path
(safety violation / hard blocker) inside a Python process.

The marker's content is the abort reason — the SessionStart banner (per
spec Inv 14 scenario 4) surfaces it to the user so they understand why the
loop halted. Idempotent: re-running with the same reason is a clean no-op;
differing reason overwrites.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Exit 0 on success; non-zero on write error or missing reason argument.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import os
import sys

MARKER = ".rabbit-auto-evolve-aborted"


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write the .rabbit-auto-evolve-aborted marker with the "
                    "given reason as its content."
    )
    parser.add_argument(
        "reason",
        help="Abort reason (surfaced by SessionStart banner).",
    )
    args = parser.parse_args()
    path = os.path.join(_repo_root(), MARKER)
    try:
        with open(path, "w") as f:
            f.write(args.reason)
    except OSError as e:
        sys.stderr.write(f"mark-aborted: write failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
