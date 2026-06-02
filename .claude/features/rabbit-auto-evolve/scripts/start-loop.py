#!/usr/bin/env python3
"""start-loop.py — write the .rabbit-auto-evolve-running marker.

Usage:
  start-loop.py

Per rabbit-auto-evolve spec.md Inv 17, all rabbit-auto-evolve runtime-marker
writes go through scripts so scope-guard (which inspects literal Bash command
strings) does not block them. This script wraps the `start` subcommand's
marker write inside a Python process.

Writes `<repo_root>/.rabbit-auto-evolve-running` with the literal content
`session` (matching the set-evolve-mode.py marker convention). Idempotent:
re-running with the marker already at the same content is a clean no-op.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Exit 0 on success; non-zero on write error.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import os
import sys

MARKER = ".rabbit-auto-evolve-running"
CONTENT = "session"


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def main() -> None:
    argparse.ArgumentParser(
        description="Write the .rabbit-auto-evolve-running marker."
    ).parse_args()
    path = os.path.join(_repo_root(), MARKER)
    try:
        with open(path, "w") as f:
            f.write(CONTENT)
    except OSError as e:
        sys.stderr.write(f"start-loop: write failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
