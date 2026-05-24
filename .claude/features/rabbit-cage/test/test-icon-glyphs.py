#!/usr/bin/env python3
"""test-icon-glyphs.py — Inv 13.

Asserts every `icon` value passed to contract.lib.runtime APIs (alert dicts
in RUNTIME entries) and every `alert-message.icon` value in CONFIGURATION
entries in rabbit-cage's feature.json is a literal renderable Unicode glyph
(non-ASCII codepoint), NOT a historical lookup name.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when Claude Code exposes native event dispatchers
that subsume contract.lib.runtime.
"""

import json
import sys
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]
CAGE_FJ = CAGE / "feature.json"

# Historical lookup names that MUST NOT appear as icon values.
HISTORICAL_NAMES = {"key", "siren", "warn", "rebuild", "unlock", "sparkle"}

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def _icon_is_glyph(icon: str) -> bool:
    """A literal renderable Unicode glyph contains at least one non-ASCII codepoint."""
    return any(ord(c) > 127 for c in icon)


def _check_icon(label: str, icon):
    if not isinstance(icon, str) or not icon:
        ko(f"{label}: icon missing or non-string ({icon!r})")
        return
    if icon in HISTORICAL_NAMES:
        ko(f"{label}: icon {icon!r} is a historical lookup name; must be a literal glyph")
        return
    if not _icon_is_glyph(icon):
        ko(f"{label}: icon {icon!r} has no non-ASCII codepoint; must be a literal glyph")
        return
    ok(f"{label}: icon {icon!r} is a literal glyph")


def main() -> int:
    data = json.loads(CAGE_FJ.read_text())

    # CONFIGURATION: every entry with alert-message MUST have a glyph icon.
    for cfg in data.get("configuration", []):
        cfg_id = cfg.get("id", "<unknown>")
        am = cfg.get("alert-message")
        if am is None:
            continue
        _check_icon(f"configuration[{cfg_id}].alert-message", am.get("icon"))

    # RUNTIME: every entry whose args carry an `alert` dict with an icon MUST have a glyph.
    runtime = data.get("runtime", {})
    for event, entries in runtime.items():
        for idx, entry in enumerate(entries):
            args = entry.get("args") or {}
            alert = args.get("alert")
            if not isinstance(alert, dict):
                continue
            if "icon" not in alert:
                continue
            api = entry.get("api", "<unknown>")
            _check_icon(f"runtime[{event}][{idx}] {api}.alert", alert.get("icon"))

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
