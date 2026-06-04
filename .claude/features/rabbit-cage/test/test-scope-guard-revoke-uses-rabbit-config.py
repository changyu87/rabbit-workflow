#!/usr/bin/env python3
"""test-scope-guard-revoke-uses-rabbit-config.py — issue #709.

The scope-guard override REVOKE instruction must point at the clean
per-feature `/rabbit-cage-config scope-guard on` command (phase 4 of #733),
NOT the raw `.claude/features/rabbit-cage/scripts/scope-guard-on.py` path.
The central `/rabbit-config scope-guard on` surface remains live during
coexistence (#769 retires it); test 4 pins that the data-driven interpreter
still dispatches the command.

Asserts four things:

  1. The scope-guard.py default-deny SESSION OVERRIDE option instructs
     revoke via `/rabbit-cage-config scope-guard on` and does NOT surface
     the raw `scripts/scope-guard-on.py` path.
  2. The active-override banner alert text (the Stop + SessionStart
     `check_marker_alert` entries for `.rabbit-scope-override`) inlines the
     `/rabbit-cage-config scope-guard on` revoke hint.
  3. rabbit-cage's feature.json declares a `scope-guard` configurable whose
     `on` value maps to `delete_marker` on `.rabbit-scope-override` (so the
     data-driven config interpreter dispatches the command).
  4. E2E (coexistence): invoking the central rabbit-config interpreter as
     `rabbit-config.py scope-guard on` actually deletes a present
     `.rabbit-scope-override` marker (re-arms default-deny).

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the scope-guard override mechanism is retired
or the /rabbit-config command interface is superseded.
"""

import glob
import json
import subprocess
import sys
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(
    subprocess.run(
        ["git", "-C", str(CAGE), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
)
SCOPE_GUARD = CAGE / "hooks" / "scope-guard.py"
CAGE_FJ = CAGE / "feature.json"
RABBIT_CONFIG = (
    REPO_ROOT / ".claude" / "features" / "rabbit-config"
    / "skills" / "rabbit-config" / "scripts" / "rabbit-config.py"
)

CLEAN_COMMAND = "/rabbit-cage-config scope-guard on"
RAW_PATH = ".claude/features/rabbit-cage/scripts/scope-guard-on.py"
OVERRIDE_MARKER = ".rabbit-scope-override"

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


def _run_scope_guard_deny():
    """Force the default-deny path; return stderr text."""
    saved = []
    paths = [
        REPO_ROOT / ".rabbit-scope-active",
        REPO_ROOT / ".rabbit-scope-override",
        REPO_ROOT / ".rabbit-scope-override-used",
    ]
    paths += [Path(p) for p in glob.glob(str(REPO_ROOT / ".rabbit-scope-active-*"))]
    for p in paths:
        if p.is_file():
            saved.append((p, p.read_text()))
            p.unlink()
    try:
        target = REPO_ROOT / ".claude/features/rabbit-cage/scripts/__deny709__.txt"
        payload = {"tool_name": "Write",
                   "tool_input": {"file_path": str(target), "content": "x"}}
        res = subprocess.run(
            [sys.executable, str(SCOPE_GUARD)],
            input=json.dumps(payload), capture_output=True, text=True,
        )
        return res.stderr
    finally:
        for p, content in saved:
            p.write_text(content)


def test_deny_message():
    stderr = _run_scope_guard_deny()
    if CLEAN_COMMAND in stderr:
        ok(f"deny message references '{CLEAN_COMMAND}'")
    else:
        ko(f"deny message missing '{CLEAN_COMMAND}' — got: {stderr!r}")
    if RAW_PATH not in stderr:
        ok("deny message does NOT surface the raw scope-guard-on.py path")
    else:
        ko(f"deny message still surfaces raw path '{RAW_PATH}'")


def _collect_override_alert_texts(data):
    """Return all check_marker_alert alert texts for .rabbit-scope-override."""
    texts = []
    runtime = data.get("runtime", {}) or {}
    for event_entries in runtime.values():
        for entry in event_entries:
            if entry.get("api") != "check_marker_alert":
                continue
            args = entry.get("args", {}) or {}
            if args.get("path") == OVERRIDE_MARKER:
                alert = args.get("alert", {}) or {}
                texts.append(alert.get("text", ""))
    return texts


def test_banner_text():
    data = json.loads(CAGE_FJ.read_text())
    texts = _collect_override_alert_texts(data)
    if not texts:
        ko("no check_marker_alert entry found for .rabbit-scope-override")
        return
    ok(f"found {len(texts)} override-banner alert entr(y/ies)")
    for t in texts:
        if CLEAN_COMMAND in t:
            ok(f"banner text inlines clean revoke command: {t!r}")
        else:
            ko(f"banner text missing '{CLEAN_COMMAND}': {t!r}")
        if RAW_PATH not in t:
            ok("banner text does NOT surface raw path")
        else:
            ko(f"banner text still surfaces raw path: {t!r}")


def test_configurable_declared():
    data = json.loads(CAGE_FJ.read_text())
    cfg = None
    for c in data.get("configuration", []):
        if c.get("subcommand") == "scope-guard":
            cfg = c
            break
    if cfg is None:
        ko("no configuration[] entry with subcommand 'scope-guard'")
        return
    ok("feature.json declares a 'scope-guard' configurable")
    on_val = (cfg.get("values") or {}).get("on")
    if on_val is None:
        ko("scope-guard configurable has no 'on' value")
        return
    if on_val.get("api") == "delete_marker":
        ok("scope-guard 'on' value uses delete_marker API")
    else:
        ko(f"scope-guard 'on' value api != delete_marker: {on_val.get('api')!r}")
    if (on_val.get("args") or {}).get("path") == OVERRIDE_MARKER:
        ok(f"scope-guard 'on' deletes {OVERRIDE_MARKER}")
    else:
        ko(f"scope-guard 'on' path != {OVERRIDE_MARKER}: {on_val.get('args')!r}")


def test_e2e_command_deletes_marker():
    """E2E: rabbit-config scope-guard on deletes a present override marker."""
    marker = REPO_ROOT / OVERRIDE_MARKER
    pre_existed = marker.is_file()
    saved = marker.read_text() if pre_existed else None
    marker.write_text("session")
    try:
        res = subprocess.run(
            [sys.executable, str(RABBIT_CONFIG), "scope-guard", "on"],
            capture_output=True, text=True,
        )
        if res.returncode == 0:
            ok("rabbit-config scope-guard on exits 0")
        else:
            ko(f"rabbit-config scope-guard on exit {res.returncode}; "
               f"stderr={res.stderr!r}")
        if not marker.is_file():
            ok("override marker deleted by the command (default-deny re-armed)")
        else:
            ko("override marker still present after command")
    finally:
        if saved is not None:
            marker.write_text(saved)
        elif marker.is_file():
            marker.unlink()


def main():
    print("test-scope-guard-revoke-uses-rabbit-config.py")
    print()
    print("=== 1. deny-message revoke instruction ===")
    test_deny_message()
    print()
    print("=== 2. active-override banner text ===")
    test_banner_text()
    print()
    print("=== 3. scope-guard configurable declared ===")
    test_configurable_declared()
    print()
    print("=== 4. E2E: command deletes override marker ===")
    test_e2e_command_deletes_marker()
    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
