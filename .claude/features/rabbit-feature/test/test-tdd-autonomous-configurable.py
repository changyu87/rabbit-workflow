#!/usr/bin/env python3
"""test-tdd-autonomous-configurable.py — Inv 57.

Pins the relocated `tdd-autonomous` configurable now declared in
rabbit-feature's OWN feature.json configuration[] (phase 3 of #733). It gates
the TDD feature-touch Step-4 human-approval cycle, so it is owned here, not by
rabbit-cage.

Asserts the declaration shape and post-#336 polarity:
  - exactly one configuration[] entry with id/subcommand == "tdd-autonomous";
  - it declares command == "rabbit-tdd-autonomous" and restart_required true;
  - storage targets the NEW canonical marker .rabbit-tdd-autonomous;
  - default == "false" (gate ACTIVE by default; no bypass marker);
  - values.false deletes .rabbit-tdd-autonomous (gate active);
  - values.true writes .rabbit-tdd-autonomous (bypass active);
  - alert-on == "true" with the exact alert text naming the skipped Step 4.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the per-feature config command is superseded by a
    native rabbit CLI configuration mechanism.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"

MARKER = ".rabbit-tdd-autonomous"
ALERT_TEXT = ("TDD-AUTONOMOUS MODE ACTIVE — TDD cycle Step 4 "
              "(human approval) skipped")

PASS = 0
FAIL = 0


def ok(msg: str) -> None:
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg: str) -> None:
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def main() -> int:
    data = json.loads(FEATURE_JSON.read_text())
    config = data.get("configuration", [])
    entries = [c for c in config if c.get("id") == "tdd-autonomous"]

    if len(entries) == 1:
        ok("exactly one tdd-autonomous configuration[] entry")
    else:
        ko(f"expected exactly one tdd-autonomous entry, got {len(entries)}")
        print(f"summary: {PASS} passed, {FAIL} failed")
        return 1

    cfg = entries[0]

    if cfg.get("subcommand") == "tdd-autonomous":
        ok("subcommand == tdd-autonomous")
    else:
        ko(f"subcommand != tdd-autonomous: {cfg.get('subcommand')!r}")

    if cfg.get("command") == "rabbit-tdd-autonomous":
        ok("command == rabbit-tdd-autonomous")
    else:
        ko(f"command != rabbit-tdd-autonomous: {cfg.get('command')!r}")

    if cfg.get("restart_required") is True:
        ok("restart_required is true")
    else:
        ko(f"restart_required != true: {cfg.get('restart_required')!r}")

    storage = cfg.get("storage", {})
    if storage.get("type") == "marker-file" and storage.get("path") == MARKER:
        ok(f"storage targets {MARKER}")
    else:
        ko(f"storage not marker-file at {MARKER}: {storage!r}")

    # Polarity: default false == gate ACTIVE (no bypass marker).
    if cfg.get("default") == "false":
        ok("default == false (Step-4 gate active by default)")
    else:
        ko(f"default != false: {cfg.get('default')!r}")

    values = cfg.get("values", {})

    false_v = values.get("false", {})
    if (false_v.get("api") == "delete_marker"
            and false_v.get("args", {}).get("path") == MARKER):
        ok(f"values.false deletes {MARKER} (gate active)")
    else:
        ko(f"values.false does not delete_marker {MARKER}: {false_v!r}")

    true_v = values.get("true", {})
    if (true_v.get("api") == "write_marker"
            and true_v.get("args", {}).get("path") == MARKER):
        ok(f"values.true writes {MARKER} (bypass active)")
    else:
        ko(f"values.true does not write_marker {MARKER}: {true_v!r}")

    if cfg.get("alert-on") == "true":
        ok("alert-on == true (alert when bypass active)")
    else:
        ko(f"alert-on != true: {cfg.get('alert-on')!r}")

    alert = cfg.get("alert-message", {})
    if alert.get("text") == ALERT_TEXT:
        ok("alert-message text matches the canonical Step-4 bypass text")
    else:
        ko(f"alert-message text mismatch: {alert.get('text')!r}")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
