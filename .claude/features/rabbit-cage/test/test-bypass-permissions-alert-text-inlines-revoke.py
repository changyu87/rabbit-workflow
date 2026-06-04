#!/usr/bin/env python3
"""test-bypass-permissions-alert-text-inlines-revoke.py — issue #324.

Pins the bypass-permissions configurable's alert-message.text to the
inlined-revoke form. Per contract Inv 47, iterate_configurables_banner emits
exactly one print_result per active override and the configurable owner is
responsible for inlining the revoke hint into the alert-message.text.

The text MUST:
  - Start with the literal mode-active prefix.
  - Use an em-dash (U+2014) as the prefix/suffix separator.
  - Inline the literal revoke command `/rabbit-cage-config bypass-permissions false`
    (migrated from `/rabbit-config` in phase 4 of #733; the central surface
    remains live during coexistence, #769 retires it).

icon (U+1F6A8 siren) and color ("red") MUST remain unchanged.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the bypass-permissions configurable is retired
or contract Inv 47 changes the per-configurable alert ownership model.
"""

import json
import sys
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]
CAGE_FJ = CAGE / "feature.json"

EXPECTED_TEXT = (
    "BYPASS-PERMISSIONS MODE ACTIVE — "
    "revoke: /rabbit-cage-config bypass-permissions false"
)
EXPECTED_ICON = "\U0001f6a8"
EXPECTED_COLOR = "red"

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


def main() -> int:
    data = json.loads(CAGE_FJ.read_text())
    bypass = None
    for cfg in data.get("configuration", []):
        if cfg.get("id") == "bypass-permissions":
            bypass = cfg
            break
    if bypass is None:
        ko("configuration[bypass-permissions] entry not found")
        print()
        print(f"summary: {PASS} passed, {FAIL} failed")
        return 1

    am = bypass.get("alert-message") or {}

    actual_text = am.get("text")
    if actual_text == EXPECTED_TEXT:
        ok("alert-message.text matches inlined-revoke form")
    else:
        ko(f"alert-message.text mismatch: {actual_text!r} != {EXPECTED_TEXT!r}")

    actual_icon = am.get("icon")
    if actual_icon == EXPECTED_ICON:
        ok("alert-message.icon unchanged (siren glyph)")
    else:
        ko(f"alert-message.icon mismatch: {actual_icon!r} != {EXPECTED_ICON!r}")

    actual_color = am.get("color")
    if actual_color == EXPECTED_COLOR:
        ok("alert-message.color unchanged (red)")
    else:
        ko(f"alert-message.color mismatch: {actual_color!r} != {EXPECTED_COLOR!r}")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
