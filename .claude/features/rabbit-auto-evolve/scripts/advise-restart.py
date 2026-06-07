#!/usr/bin/env python3
"""advise-restart.py — advisory-restart marker lifecycle.

Per rabbit-auto-evolve spec.md Inv 52 (added v0.42.0 for issue #545), this CLI
owns the `.rabbit-auto-evolve-restart-advised` marker. The advisory marker is a
structured, persistently-surfaced restart signal that mirrors the HARD
`.rabbit-auto-evolve-restart-needed` marker (Inv 8 / Inv 31) but is ADVISORY:
it records that a restart WOULD unlock a capability (e.g. "activates
skill-creator + code-review; enables worktree.baseRef for parallel dispatch"),
yet it NEVER pauses, blocks, holds, or auto-resumes the loop. The two markers
are independent — this script touches only the advisory marker.

Per Inv 17, all rabbit-auto-evolve runtime-marker writes go through scripts so
scope-guard (which inspects literal Bash command strings) does not block them.

Subcommands:

  write <reason>   Write `.rabbit-auto-evolve-restart-advised` at the repo root
                   with the structured reason string as its content. Overwrites
                   if present (latest reason wins). Missing reason -> non-zero
                   exit. Mirrors mark-restart-needed.py / mark-aborted.py.

  status           Emit a JSON object on stdout describing the marker's
                   presence and reason. ALWAYS exit 0 — the verdict is carried
                   in the payload, never the exit code (mirrors
                   check-auto-resume.py). Present:
                     {"advised": true, "reason": "<content>"}
                   Absent (graceful):
                     {"advised": false}
                   This is the INVOKE surface rabbit-cage's Stop/SessionStart
                   dispatcher calls to surface the advisory restart line
                   cross-feature (contract.md provides.scripts).

  clear            Remove the marker. Idempotent: a missing marker is a clean
                   no-op (exit 0). This is the INVOKE surface rabbit-cage's
                   SessionStart calls to clear the advisory after the advised
                   restart has occurred.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests. The script reads/writes only
the advisory marker and never reads, writes, or deletes
`.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`, or
`.rabbit-auto-evolve-running`.

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

MARKER = ".rabbit-auto-evolve-restart-advised"


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _marker_path() -> str:
    return os.path.join(_repo_root(), MARKER)


def _cmd_write(args: argparse.Namespace) -> int:
    try:
        with open(_marker_path(), "w") as f:
            f.write(args.reason)
    except OSError as e:
        sys.stderr.write(f"advise-restart: write failed: {e}\n")
        return 1
    return 0


def _cmd_status(_args: argparse.Namespace) -> int:
    path = _marker_path()
    if os.path.exists(path):
        try:
            reason = open(path).read()
        except OSError as e:
            sys.stderr.write(f"advise-restart: read failed: {e}\n")
            result = {"advised": False}
        else:
            result = {"advised": True, "reason": reason}
    else:
        result = {"advised": False}
    print(json.dumps(result, indent=2))
    return 0


def _cmd_clear(_args: argparse.Namespace) -> int:
    path = _marker_path()
    try:
        os.remove(path)
    except FileNotFoundError:
        pass  # idempotent: missing marker is a clean no-op
    except OSError as e:
        sys.stderr.write(f"advise-restart: clear failed: {e}\n")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Manage the advisory-restart marker "
            "(.rabbit-auto-evolve-restart-advised). ADVISORY only — never "
            "pauses the loop; distinct from the hard restart-needed marker."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser(
        "write", help="Write the advisory marker with the given reason."
    )
    p_write.add_argument(
        "reason",
        help="Structured reason describing the capability a restart unlocks.",
    )
    p_write.set_defaults(func=_cmd_write)

    p_status = sub.add_parser(
        "status",
        help="Emit {advised, reason?} JSON on stdout (always exit 0).",
    )
    p_status.set_defaults(func=_cmd_status)

    p_clear = sub.add_parser(
        "clear", help="Remove the advisory marker (idempotent)."
    )
    p_clear.set_defaults(func=_cmd_clear)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
