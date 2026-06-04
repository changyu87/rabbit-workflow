#!/usr/bin/env python3
"""test-tdd-autonomous-configurable.py — issue #336 (phase 2 of #733).

Pins the rename + polarity flip of rabbit-cage's TDD-gating configurable from
`human-approval` to `tdd-autonomous`. Per the issue's table and the CLI
positive-streamlined naming rule (contract Inv 12):

  | old                          | new                       | meaning              |
  | ---------------------------- | ------------------------- | -------------------- |
  | human-approval true (default)| tdd-autonomous false      | gate active (Step 4) |
  | human-approval false         | tdd-autonomous true       | bypass active        |

The marker PATH (`.rabbit-human-approval-bypass`) is UNCHANGED — marker
dual-read coexistence already landed in #766; only the user-facing subcommand
name + boolean polarity change here.

Asserts:
  1. feature.json declares a configurable with subcommand `tdd-autonomous`
     and NO surviving `human-approval` subcommand/id.
  2. Polarity flip: `false` is the default and deletes the bypass marker
     (gate active); `true` writes the bypass marker (bypass active).
  3. `alert-on` is `true` (bypass is the positive/alerting state) and the
     alert-message.text reflects the new TDD-AUTONOMOUS framing.
  4. E2E: invoking the data-driven rabbit-config interpreter as
     `rabbit-config.py tdd-autonomous true` writes the bypass marker, and
     `tdd-autonomous false` deletes it.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the tdd-autonomous configurable is retired or the
/rabbit-config command interface is superseded.
"""

import json
import subprocess
import sys
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]
CAGE_FJ = CAGE / "feature.json"
REPO_ROOT = Path(
    subprocess.run(
        ["git", "-C", str(CAGE), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
)
RABBIT_CONFIG = (
    REPO_ROOT / ".claude" / "features" / "rabbit-config"
    / "skills" / "rabbit-config" / "scripts" / "rabbit-config.py"
)

MARKER = ".rabbit-human-approval-bypass"
EXPECTED_ALERT_TEXT = (
    "TDD-AUTONOMOUS MODE ACTIVE — TDD cycle Step 4 (human approval) skipped"
)

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def _find_cfg(data, subcommand):
    for cfg in data.get("configuration", []):
        if cfg.get("subcommand") == subcommand:
            return cfg
    return None


def test_renamed():
    data = json.loads(CAGE_FJ.read_text())
    if _find_cfg(data, "tdd-autonomous") is not None:
        ok("feature.json declares subcommand 'tdd-autonomous'")
    else:
        ko("no configuration[] entry with subcommand 'tdd-autonomous'")
    if _find_cfg(data, "human-approval") is None:
        ok("old subcommand 'human-approval' is gone")
    else:
        ko("old subcommand 'human-approval' still present")
    ids = {c.get("id") for c in data.get("configuration", [])}
    if "human-approval" not in ids:
        ok("no configurable id 'human-approval' remains")
    else:
        ko("configurable id 'human-approval' still present")


def test_polarity():
    data = json.loads(CAGE_FJ.read_text())
    cfg = _find_cfg(data, "tdd-autonomous")
    if cfg is None:
        ko("polarity: tdd-autonomous configurable not found")
        return
    values = cfg.get("values") or {}

    if cfg.get("default") == "false":
        ok("default is 'false' (gate active, like old default)")
    else:
        ko(f"default != 'false': {cfg.get('default')!r}")

    false_val = values.get("false") or {}
    if false_val.get("api") == "delete_marker" and \
            (false_val.get("args") or {}).get("path") == MARKER:
        ok("'false' deletes the bypass marker (gate active)")
    else:
        ko(f"'false' value wrong: {false_val!r}")

    true_val = values.get("true") or {}
    if true_val.get("api") == "write_marker" and \
            (true_val.get("args") or {}).get("path") == MARKER:
        ok("'true' writes the bypass marker (bypass active)")
    else:
        ko(f"'true' value wrong: {true_val!r}")

    if (cfg.get("storage") or {}).get("path") == MARKER:
        ok(f"storage marker path unchanged ({MARKER})")
    else:
        ko(f"storage path changed: {(cfg.get('storage') or {}).get('path')!r}")


def test_alert():
    data = json.loads(CAGE_FJ.read_text())
    cfg = _find_cfg(data, "tdd-autonomous")
    if cfg is None:
        ko("alert: tdd-autonomous configurable not found")
        return
    if cfg.get("alert-on") == "true":
        ok("alert-on flipped to 'true' (bypass is the alerting state)")
    else:
        ko(f"alert-on != 'true': {cfg.get('alert-on')!r}")
    text = (cfg.get("alert-message") or {}).get("text")
    if text == EXPECTED_ALERT_TEXT:
        ok("alert-message.text matches new TDD-AUTONOMOUS framing")
    else:
        ko(f"alert-message.text mismatch: {text!r} != {EXPECTED_ALERT_TEXT!r}")


def _run_config(value):
    return subprocess.run(
        [sys.executable, str(RABBIT_CONFIG), "tdd-autonomous", value],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )


def test_e2e():
    marker = REPO_ROOT / MARKER
    pre_existed = marker.is_file()
    saved = marker.read_text() if pre_existed else None
    try:
        if marker.is_file():
            marker.unlink()
        res = _run_config("true")
        if res.returncode == 0 and marker.is_file():
            ok("rabbit-config tdd-autonomous true writes the bypass marker")
        else:
            ko(f"true did not write marker: rc={res.returncode}, "
               f"present={marker.is_file()}, stderr={res.stderr!r}")
        res = _run_config("false")
        if res.returncode == 0 and not marker.is_file():
            ok("rabbit-config tdd-autonomous false deletes the bypass marker")
        else:
            ko(f"false did not delete marker: rc={res.returncode}, "
               f"present={marker.is_file()}, stderr={res.stderr!r}")
    finally:
        if saved is not None:
            marker.write_text(saved)
        elif marker.is_file():
            marker.unlink()


def main():
    print("test-tdd-autonomous-configurable.py")
    print()
    print("=== 1. rename ===")
    test_renamed()
    print()
    print("=== 2. polarity flip ===")
    test_polarity()
    print()
    print("=== 3. alert ===")
    test_alert()
    print()
    print("=== 4. E2E interpreter round-trip ===")
    test_e2e()
    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
