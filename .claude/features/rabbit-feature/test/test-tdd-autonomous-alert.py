#!/usr/bin/env python3
"""test-tdd-autonomous-alert.py — Inv 59 (e2e).

The tdd-autonomous bypass override is re-homed here as a PER-FEATURE runtime[]
alert (phase 3 of #733): rabbit-feature emits its own Stop AND SessionStart
alert when the .rabbit-tdd-autonomous bypass marker is active, replacing
rabbit-config's central iterate_configurables_* enumeration. The alert is
consumed by rabbit-cage's generic event dispatcher via
contract.lib.runtime.check_marker_alert.

Asserts:
  (i)   feature.json runtime declares a check_marker_alert entry under BOTH
        Stop and SessionStart targeting .rabbit-tdd-autonomous with the
        canonical Step-4 bypass alert text;
  (ii)  driving that declared entry through contract.lib.runtime fires a red
        print_result when the marker is present;
  (iii) the same entry is silent (ok_result, no banner) when the marker is
        absent.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the per-feature config command is superseded by a
    native rabbit CLI configuration mechanism.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FEATURE_JSON = REPO / ".claude/features/rabbit-feature/feature.json"

# Allow `from contract.lib import runtime` from the live tree.
sys.path.insert(0, str(REPO / ".claude/features"))

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


def _find_alert_entry(runtime: dict, event: str):
    """Return the check_marker_alert entry under `event` targeting MARKER."""
    for entry in runtime.get(event, []):
        if (entry.get("api") == "check_marker_alert"
                and entry.get("args", {}).get("path") == MARKER):
            return entry
    return None


def main() -> int:
    data = json.loads(FEATURE_JSON.read_text())
    runtime_decl = data.get("runtime", {})

    entries = {}
    for event in ("Stop", "SessionStart"):
        entry = _find_alert_entry(runtime_decl, event)
        if entry is None:
            ko(f"runtime.{event} has no check_marker_alert for {MARKER}")
            continue
        ok(f"runtime.{event} declares a check_marker_alert for {MARKER}")
        alert = entry.get("args", {}).get("alert", {})
        if alert.get("text") == ALERT_TEXT:
            ok(f"runtime.{event} alert text matches canonical Step-4 text")
        else:
            ko(f"runtime.{event} alert text mismatch: {alert.get('text')!r}")
        if alert.get("color") == "red":
            ok(f"runtime.{event} alert color is red")
        else:
            ko(f"runtime.{event} alert color != red: {alert.get('color')!r}")
        entries[event] = entry

    # Drive the declared entries through contract.lib.runtime e2e.
    from contract.lib import runtime  # type: ignore

    for event, entry in entries.items():
        args = entry["args"]
        # (ii) marker present -> red print_result fires.
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / MARKER).write_text("session")
            result = runtime.check_marker_alert(
                path=args["path"],
                content=args.get("content"),
                alert=args["alert"],
                repo_root=td,
            )
            if (result.get("type") == "print"
                    and result.get("text") == ALERT_TEXT
                    and result.get("color") == "red"):
                ok(f"{event}: alert FIRES when {MARKER} is present")
            else:
                ko(f"{event}: alert did not fire correctly: {result!r}")

        # (iii) marker absent -> silent (ok_result, no banner).
        with tempfile.TemporaryDirectory() as td:
            result = runtime.check_marker_alert(
                path=args["path"],
                content=args.get("content"),
                alert=args["alert"],
                repo_root=td,
            )
            if result.get("type") != "print":
                ok(f"{event}: alert SILENT when {MARKER} is absent")
            else:
                ko(f"{event}: alert unexpectedly fired with no marker: {result!r}")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
