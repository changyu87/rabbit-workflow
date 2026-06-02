#!/usr/bin/env python3
"""check-preconditions.py — report on the three `start` preconditions.

Per rabbit-auto-evolve spec.md Inv 21 (added v0.7.3 for issue #375),
this CLI inspects the three preconditions required for
`/rabbit-auto-evolve start` and emits a structured JSON report on stdout:

  {
    "all_pass": <bool>,
    "checks": [
      {"id": "active-marker",       "ok": <bool>, "detail": "<...>"},
      {"id": "approval-bypass",     "ok": <bool>, "detail": "<...>"},
      {"id": "bypass-permissions",  "ok": <bool>, "detail": "<...>"}
    ]
  }

Exit code is ALWAYS 0 — the verdict lives in `all_pass`, not in the exit
code. The script reads files only (`os.path.exists` plus a JSON parse of
`.claude/settings.local.json`) and never invokes `ls`, `test -f`, or any
other command that would exit non-zero on the expected "not yet activated"
path. The three check IDs (`active-marker`, `approval-bypass`,
`bypass-permissions`) are stable identifiers; callers may rely on their
presence and order.

The detail strings include the actionable next step (`/rabbit-auto-evolve
on`, restart Claude, etc.) so SKILL.md can surface them verbatim.

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ACTIVE_MARKER = ".rabbit-auto-evolve-active"
APPROVAL_BYPASS_MARKER = ".rabbit-human-approval-bypass"
SETTINGS_PATH = os.path.join(".claude", "settings.local.json")


def _repo_root() -> str:
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT") or os.getcwd()


def _check_active(repo_root: str) -> dict:
    path = os.path.join(repo_root, ACTIVE_MARKER)
    if os.path.exists(path):
        return {
            "id": "active-marker",
            "ok": True,
            "detail": f"{ACTIVE_MARKER} present",
        }
    return {
        "id": "active-marker",
        "ok": False,
        "detail": f"{ACTIVE_MARKER} missing — run /rabbit-auto-evolve on",
    }


def _check_approval_bypass(repo_root: str) -> dict:
    path = os.path.join(repo_root, APPROVAL_BYPASS_MARKER)
    if os.path.exists(path):
        return {
            "id": "approval-bypass",
            "ok": True,
            "detail": f"{APPROVAL_BYPASS_MARKER} present (human-approval off)",
        }
    return {
        "id": "approval-bypass",
        "ok": False,
        "detail": f"{APPROVAL_BYPASS_MARKER} missing — run /rabbit-auto-evolve on",
    }


def _check_bypass_permissions(repo_root: str) -> dict:
    path = os.path.join(repo_root, SETTINGS_PATH)
    if not os.path.exists(path):
        return {
            "id": "bypass-permissions",
            "ok": False,
            "detail": (
                f"{SETTINGS_PATH} missing — run /rabbit-auto-evolve on and "
                "restart Claude"
            ),
        }
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        return {
            "id": "bypass-permissions",
            "ok": False,
            "detail": (
                f"{SETTINGS_PATH} unreadable ({e}) — re-run /rabbit-auto-evolve on"
            ),
        }
    mode = None
    if isinstance(data, dict):
        permissions = data.get("permissions")
        if isinstance(permissions, dict):
            mode = permissions.get("defaultMode")
    if mode == "bypassPermissions":
        return {
            "id": "bypass-permissions",
            "ok": True,
            "detail": (
                f"{SETTINGS_PATH} permissions.defaultMode == 'bypassPermissions'"
            ),
        }
    return {
        "id": "bypass-permissions",
        "ok": False,
        "detail": (
            f"permissions.defaultMode != bypassPermissions in {SETTINGS_PATH} — "
            "restart Claude after /rabbit-auto-evolve on"
        ),
    }


def main() -> None:
    argparse.ArgumentParser(
        description=(
            "Report on the three /rabbit-auto-evolve start preconditions as "
            "JSON. Exit code is always 0; the verdict lives in `all_pass`."
        )
    ).parse_args()
    root = _repo_root()
    checks = [
        _check_active(root),
        _check_approval_bypass(root),
        _check_bypass_permissions(root),
    ]
    report = {
        "all_pass": all(c["ok"] for c in checks),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
