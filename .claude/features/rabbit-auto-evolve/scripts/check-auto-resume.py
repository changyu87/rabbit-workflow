#!/usr/bin/env python3
"""check-auto-resume.py — mechanical restart-resume detection.

Per rabbit-auto-evolve spec.md Inv 31 (added v0.19.0 for issue #424), this
CLI inspects rabbit-auto-evolve's runtime markers at the repo root and emits a
JSON object on stdout describing whether the loop should auto-resume after a
Claude restart. Always exits 0.

Today's restart recovery is convention-enforced: after a `restart-needed` tick
the human must read the SessionStart banner (Inv 22) and manually paste
`/rabbit-auto-evolve start`. A missed read silently stalls the loop. Per
spec-rules §1 (`script > CLI > spec > prompt`) the resume decision is moved out
of human convention and into this deterministic script so the SessionStart
hook can mechanically self-resume.

Auto-resume conditions (ALL three must hold for `resume: true`):

  1. `.rabbit-auto-evolve-active` is present (mode is on), AND
  2. `.rabbit-auto-evolve-restart-needed` is present (a restart was needed),
     AND
  3. `.rabbit-auto-evolve-running` is NOT present (no tick already running).

When all three hold:

  {"resume": true, "action": "/rabbit-auto-evolve start"}

otherwise:

  {"resume": false, "action": null}

The `.rabbit-auto-evolve-aborted` marker is NOT consulted here — abort handling
is the banner's responsibility (Inv 22); this script answers only the narrow
"should we mechanically re-launch the loop after a restart" question.

The script reads files only (`os.path.exists`) and never invokes `ls`,
`test -f`, or any command that would exit non-zero on the expected "not
active" path. `<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

rabbit-cage integration (cross-scope INVOKE, NOT a feature edit): the
SessionStart hook is owned by rabbit-cage. It should INVOKE this script and,
when `resume` is true, surface the `action` so the loop auto-resumes. That
hook wiring is a SEPARATE rabbit-cage touch (discovered issue), out of this
feature's scope.

Exit code is ALWAYS 0 — the verdict is carried in `resume`.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ACTIVE_MARKER = ".rabbit-auto-evolve-active"
RESTART_MARKER = ".rabbit-auto-evolve-restart-needed"
RUNNING_MARKER = ".rabbit-auto-evolve-running"

RESUME_ACTION = "/rabbit-auto-evolve start"


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _should_resume(repo_root: str) -> bool:
    active = os.path.exists(os.path.join(repo_root, ACTIVE_MARKER))
    restart_needed = os.path.exists(os.path.join(repo_root, RESTART_MARKER))
    running = os.path.exists(os.path.join(repo_root, RUNNING_MARKER))
    return active and restart_needed and not running


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "Inspect rabbit-auto-evolve runtime markers and emit whether the "
            "loop should auto-resume after a Claude restart "
            "({resume, action}). Exit code is always 0."
        )
    ).parse_args()

    root = _repo_root()
    if _should_resume(root):
        result = {"resume": True, "action": RESUME_ACTION}
    else:
        result = {"resume": False, "action": None}
    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
