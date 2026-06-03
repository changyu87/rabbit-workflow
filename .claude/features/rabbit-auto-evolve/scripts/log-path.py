#!/usr/bin/env python3
"""log-path.py — print the absolute path of the per-tick observability log
(Inv 37, issue #404).

Prints the absolute path of `<state_dir>/auto-evolve.log` (state dir via
`RABBIT_AUTO_EVOLVE_STATE_DIR`, else `<cwd>/.rabbit`) on stdout, so a
cross-session daemon can `tail -f $(python3 …/log-path.py)` without
round-tripping to the running Claude session.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import os
import sys

LOG_NAME = "auto-evolve.log"


def _state_dir():
    override = os.environ.get("RABBIT_AUTO_EVOLVE_STATE_DIR")
    if override:
        return override
    return os.path.join(os.getcwd(), ".rabbit")


def main():
    argparse.ArgumentParser(
        description="Print the absolute path of the .rabbit/auto-evolve.log "
                    "per-tick observability log (Inv 37 / #404). Honors "
                    "RABBIT_AUTO_EVOLVE_STATE_DIR."
    ).parse_args()
    print(os.path.abspath(os.path.join(_state_dir(), LOG_NAME)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
