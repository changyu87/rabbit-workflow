#!/usr/bin/env python3
"""_runtime_flags.py — single source of truth for runtime-override flag text.

RABBIT-CAGE-BACKLOG-27 / Inv 61, 62. Both `sync-check.py` (Stop-time alert)
and `session-init.py` (startup-banner status-flags block) need to surface
the SAME canonical message text for every active runtime override. Hosting
the text and detection logic here prevents drift between the two producers:
when a flag's wording (or a new flag) changes, exactly one file is edited.

Public API:
    CANONICAL_FLAG_BODIES: dict[str, str] — per-flag canonical body text,
        keyed by flag id (`bypass_permissions`, `human_approval`). The
        dict is the test-facing API; callers do NOT import the per-flag
        bare-name constants.
    active_flags(repo_root) -> list[dict] — every active flag in priority
        order; each dict carries `body` (canonical alert text) and `revoke`
        (canonical `/rabbit-config <subcmd> <value>` revoke command).
    log_exc(script_tag, where, exc) — BACKLOG-28: shared exception logger
        used by every multi-condition hook (sync-check.py, session-init.py)
        in place of bare `except Exception: pass`. Centralising this keeps
        Inv 50 honoured in exactly one location.

Implementation notes
--------------------
* No ANSI escape codes, no `[rabbit]` brand prefix, no `━━━` bar appear in
  this file — Inv 87 forbids those tokens in hook source files. Callers
  wrap the returned text via `rabbit_subline(..., color="red")` from the
  shared renderer, which is the sole authorized formatter.
* The bypass-permissions detection reads `.claude/settings.local.json`
  directly (per Inv 61). A missing file or malformed JSON is treated as
  "not active" rather than raising — the hooks must keep their exit-0
  happy-path contract.
* The per-flag bare-name constants are underscore-prefixed (private). The
  public dict `CANONICAL_FLAG_BODIES` is the only entry point for callers
  that need the body strings directly (currently the test suite).

Version: 1.1.0
Owner: rabbit-workflow team
Deprecation criterion: when both hooks are refactored into a unified
    rabbit-cage status-emission library that owns the alert text itself.
"""

import json
import sys
from pathlib import Path


_BYPASS_PERMISSIONS_BODY = (
    "BYPASS-PERMISSIONS MODE ACTIVE — Claude Code native per-write prompts "
    "skipped; scope-guard hook is the sole write-authorization gate"
)
_BYPASS_PERMISSIONS_REVOKE = "/rabbit-config bypass-permissions false"

_HUMAN_APPROVAL_BODY = (
    "HUMAN APPROVAL BYPASS ACTIVE — Step 4 skipped for all "
    "rabbit-feature-touch dispatches"
)
_HUMAN_APPROVAL_REVOKE = "/rabbit-config human-approval true"


# Public test-facing API: lookup canonical body text by flag id. Both
# producers (sync-check.py, session-init.py) and the rabbit-cage test
# suite read from this dict so the wording cannot drift between sites.
CANONICAL_FLAG_BODIES = {
    "bypass_permissions": _BYPASS_PERMISSIONS_BODY,
    "human_approval": _HUMAN_APPROVAL_BODY,
}


def log_exc(script_tag: str, where: str, exc: BaseException) -> None:
    """BACKLOG-17 / Inv 50 / BACKLOG-28: shared exception logger.

    Hooks call this from the formerly-silent error-handler arms (in place of
    bare `except Exception: pass`). Output goes to stderr only; the hook's
    exit-0 happy-path contract is preserved. Centralising the implementation
    keeps Inv 50's wording consistent across every multi-condition hook.
    """
    try:
        sys.stderr.write(f"[{script_tag}] {where}: {type(exc).__name__}: {exc}\n")
    except Exception:
        pass


def is_bypass_permissions_active(repo_root) -> bool:
    """Inv 61. True iff `.claude/settings.local.json` declares
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
    """Inv 39. True iff `.rabbit-human-approval-bypass` exists at repo root."""
    return (Path(repo_root) / ".rabbit-human-approval-bypass").is_file()


def active_flags(repo_root) -> list:
    """Return one entry per active runtime override, in the conditional-priority
    order declared by Inv 83 (human-approval before bypass-permissions). Each
    entry is `{"body": <canonical text>, "revoke": <revoke command>}`. Empty
    list when no flags are active (caller MUST then omit the block — Inv 62)."""
    flags = []
    if is_human_approval_bypass_active(repo_root):
        flags.append({
            "body": _HUMAN_APPROVAL_BODY,
            "revoke": _HUMAN_APPROVAL_REVOKE,
        })
    if is_bypass_permissions_active(repo_root):
        flags.append({
            "body": _BYPASS_PERMISSIONS_BODY,
            "revoke": _BYPASS_PERMISSIONS_REVOKE,
        })
    return flags
