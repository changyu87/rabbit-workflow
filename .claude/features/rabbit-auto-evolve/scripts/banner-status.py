#!/usr/bin/env python3
"""banner-status.py — owns the active-banner line-2 text variants.

Per rabbit-auto-evolve spec.md Inv 22 (added v0.7.5 for issue #380),
this CLI inspects rabbit-auto-evolve's runtime markers at the repo root
and emits a JSON object on stdout describing the active banner. Always
exits 0.

When `.rabbit-auto-evolve-active` is absent:

  {"active": false, "line1": null, "line2": null}

When `.rabbit-auto-evolve-active` is present:

  {
    "active": true,
    "line1": {"text": "AUTONOMOUS-EVOLVE MODE ACTIVE", "icon": "...", "color": "red"},
    "line2": {"text": "<per precedence>", "icon": "...", "color": "..."}
  }

Line-2 precedence (first match wins):

  | adjunct marker(s)                       | substring                            | icon | color  |
  |-----------------------------------------|--------------------------------------|------|--------|
  | .rabbit-auto-evolve-aborted (highest)   | loop aborted on safety violation     | 🛑   | red    |
  | .rabbit-auto-evolve-restart-needed      | resume after restart                 | 🔁   | yellow |
  | .rabbit-auto-evolve-running             | loop in progress                     | 🔄   | yellow |
  | none, state-file ABSENT (#793)          | auto-evolve configured — restart …   | ⏸    | yellow |
  | none, state-file PRESENT                | paste: /rabbit-auto-evolve start     | ▶    | yellow |

The two `none` sub-cases (#793) split the lowest-priority branch by the
presence of `.rabbit/auto-evolve-state.json` (only start-loop.py creates it on
the first `start`). ABSENT means the post-`on`/pre-`start` window — configured
but never started, a restart is pending — so the restart-pending line2 is
emitted VERBATIM the same as the symmetric Stop line
(`contract.lib.runtime.emit_auto_evolve_stop_line`, Inv 55) so SessionStart
and Stop agree. PRESENT retains the existing idle/active line.

Marker file contents (for aborted/restart-needed) are surfaced in the line2
text alongside the literal substring above when non-empty.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Ownership migration (v0.7.5): the current `contract.lib.runtime`
`emit_auto_evolve_banner` implementation still inlines the three pre-existing
variants (aborted / restart-needed / default) and does NOT yet call this
script. A follow-up cycle against the `contract` feature will refactor it to
invoke `banner-status.py` instead. Until that follow-up lands, the `running`
variant exists in this script but is NOT surfaced at SessionStart.

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

ACTIVE_MARKER = ".rabbit-auto-evolve-active"
RUNNING_MARKER = ".rabbit-auto-evolve-running"
RESTART_MARKER = ".rabbit-auto-evolve-restart-needed"
ABORTED_MARKER = ".rabbit-auto-evolve-aborted"

# #793: the loop-started signal. Only start-loop.py creates this on the first
# `start`; its ABSENCE marks the post-`on`/pre-`start` window (never started).
STATE_FILE = os.path.join(".rabbit", "auto-evolve-state.json")

# #793: restart-pending line2 — VERBATIM the same as the Stop line in
# contract.lib.runtime so SessionStart and Stop agree.
RESTART_PENDING_TEXT = (
    "auto-evolve configured — restart Claude Code, then run "
    "/rabbit-auto-evolve start"
)


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _read_marker_reason(path: str) -> str:
    """Return stripped marker file content, or empty string on read failure."""
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _line2(repo_root: str) -> dict:
    aborted_path = os.path.join(repo_root, ABORTED_MARKER)
    if os.path.exists(aborted_path):
        reason = _read_marker_reason(aborted_path)
        base = "loop aborted on safety violation"
        if reason and reason != "session":
            text = f"{base} — {reason} — clear .rabbit-auto-evolve-aborted to resume"
        else:
            text = f"{base} — clear .rabbit-auto-evolve-aborted to resume"
        return {"text": text, "icon": "🛑", "color": "red"}

    restart_path = os.path.join(repo_root, RESTART_MARKER)
    if os.path.exists(restart_path):
        reason = _read_marker_reason(restart_path)
        base = "resume after restart: paste /rabbit-auto-evolve start"
        if reason and reason != "session":
            text = f"{base} (reason: {reason})"
        else:
            text = base
        return {"text": text, "icon": "🔁", "color": "yellow"}

    running_path = os.path.join(repo_root, RUNNING_MARKER)
    if os.path.exists(running_path):
        text = (
            "loop in progress — /rabbit-auto-evolve stop to halt, or wait "
            "for the current tick to complete"
        )
        return {"text": text, "icon": "🔄", "color": "yellow"}

    # #793: no priority marker — distinguish never-started (state file absent,
    # restart pending) from started-then-idle (state file present).
    if not os.path.isfile(os.path.join(repo_root, STATE_FILE)):
        return {"text": RESTART_PENDING_TEXT, "icon": "⏸", "color": "yellow"}

    return {
        "text": "paste: /rabbit-auto-evolve start",
        "icon": "▶",
        "color": "yellow",
    }


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "Inspect rabbit-auto-evolve runtime markers and emit the active "
            "banner JSON ({active, line1, line2}). Exit code is always 0."
        )
    ).parse_args()

    root = _repo_root()
    active_path = os.path.join(root, ACTIVE_MARKER)
    if not os.path.exists(active_path):
        print(json.dumps({"active": False, "line1": None, "line2": None}, indent=2))
        sys.exit(0)

    line1 = {
        "text": "AUTONOMOUS-EVOLVE MODE ACTIVE",
        "icon": "🤖",
        "color": "red",
    }
    line2 = _line2(root)
    print(
        json.dumps(
            {"active": True, "line1": line1, "line2": line2},
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
