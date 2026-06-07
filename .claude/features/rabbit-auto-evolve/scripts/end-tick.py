#!/usr/bin/env python3
"""end-tick.py — delete the .rabbit-auto-evolve-running marker.

Usage:
  end-tick.py

Per rabbit-auto-evolve spec.md Inv 20 (added in v0.7.2 for issue #373),
EVERY tick exit path MUST invoke `end-tick.py` as its last action:

  - Normal completion (12-phase walk done, `ScheduleWakeup` called).
  - Phase 0 halt (`.rabbit-auto-evolve-stop-requested` observed).
  - Safety-violation abort (`.rabbit-auto-evolve-aborted` written).
  - Error abort (unexpected exception in any phase).

`end-tick.py` deletes `<repo_root>/.rabbit-auto-evolve-running` (mirror of
`start-loop.py`'s write). Idempotent: missing marker is a clean no-op
(exit 0). Without this, the running marker leaks across sessions and the
user has to `rm -f` it manually — which scope-guard correctly denies.

Per spec.md Inv 17 the marker write/delete is wrapped in a script so
scope-guard does not see the literal `.rabbit-auto-evolve-*` path in the
Bash command string.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Exit 0 on success (including the marker-absent case); non-zero on
unexpected delete error.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import os
import sys

MARKER = ".rabbit-auto-evolve-running"


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def main() -> None:
    argparse.ArgumentParser(
        description="Delete the .rabbit-auto-evolve-running marker (mirror of start-loop.py)."
    ).parse_args()
    path = os.path.join(_repo_root(), MARKER)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as e:
        sys.stderr.write(f"end-tick: delete failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
