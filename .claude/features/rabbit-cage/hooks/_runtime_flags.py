#!/usr/bin/env python3
"""_runtime_flags.py — single source of truth for runtime-override flag text.

RABBIT-CAGE-BACKLOG-27 / Inv 88, 89. Both `sync-check.py` (Stop-time alert)
and `session-init.py` (startup-banner status-flags block) need to surface
the SAME canonical message text for every active runtime override. Hosting
the text and detection logic here prevents drift between the two producers:
when a flag's wording (or a new flag) changes, exactly one file is edited.

Public API:
    BYPASS_PERMISSIONS_BODY: str  — canonical Stop/Startup body for Inv 88.
    HUMAN_APPROVAL_BODY: str      — canonical Stop body for Inv 59.
    active_flags(repo_root) -> list[dict] — every active flag in priority
        order; each dict carries `body` (canonical alert text) and `revoke`
        (canonical `/rabbit-config <subcmd> <value>` revoke command).

Implementation notes
--------------------
* No ANSI escape codes, no `[rabbit]` brand prefix, no `━━━` bar appear in
  this file — Inv 77 forbids those tokens in hook source files. Callers
  wrap the returned text via `rabbit_subline(..., color="red")` from the
  shared renderer, which is the sole authorized formatter.
* The bypass-permissions detection reads `.claude/settings.local.json`
  directly (per Inv 88). A missing file or malformed JSON is treated as
  "not active" rather than raising — the hooks must keep their exit-0
  happy-path contract.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when both hooks are refactored into a unified
    rabbit-cage status-emission library that owns the alert text itself.
"""

import json
from pathlib import Path


BYPASS_PERMISSIONS_BODY = (
    "BYPASS-PERMISSIONS MODE ACTIVE — Claude Code native per-write prompts "
    "skipped; scope-guard hook is the sole write-authorization gate"
)
BYPASS_PERMISSIONS_REVOKE = "/rabbit-config bypass-permissions false"

HUMAN_APPROVAL_BODY = (
    "HUMAN APPROVAL BYPASS ACTIVE — Step 4 skipped for all "
    "rabbit-feature-touch dispatches"
)
HUMAN_APPROVAL_REVOKE = "/rabbit-config human-approval true"


def is_bypass_permissions_active(repo_root) -> bool:
    """Inv 88. True iff `.claude/settings.local.json` declares
    permissions.defaultMode == "bypassPermissions". Missing file, malformed
    JSON, or any other shape returns False."""
    settings_path = Path(repo_root) / ".claude" / "settings.local.json"
    if not settings_path.is_file():
        return False
    try:
        data = json.loads(settings_path.read_text())
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return False
    return perms.get("defaultMode") == "bypassPermissions"


def is_human_approval_bypass_active(repo_root) -> bool:
    """Inv 59. True iff `.rabbit-human-approval-bypass` exists at repo root."""
    return (Path(repo_root) / ".rabbit-human-approval-bypass").is_file()


def active_flags(repo_root) -> list:
    """Return one entry per active runtime override, in the conditional-priority
    order declared by Inv 37 (human-approval before bypass-permissions). Each
    entry is `{"body": <canonical text>, "revoke": <revoke command>}`. Empty
    list when no flags are active (caller MUST then omit the block — Inv 89)."""
    flags = []
    if is_human_approval_bypass_active(repo_root):
        flags.append({
            "body": HUMAN_APPROVAL_BODY,
            "revoke": HUMAN_APPROVAL_REVOKE,
        })
    if is_bypass_permissions_active(repo_root):
        flags.append({
            "body": BYPASS_PERMISSIONS_BODY,
            "revoke": BYPASS_PERMISSIONS_REVOKE,
        })
    return flags
