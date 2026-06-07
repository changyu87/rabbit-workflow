#!/usr/bin/env python3
"""test-display-timezone-configurable.py — spec Inv 51.

Asserts the shape of rabbit-cage's `display-timezone` configurable[] entry — a
free-scalar json-key configurable (default `local`, stored at
`env.RABBIT_DISPLAY_TIMEZONE` in `.claude/settings.local.json`), set via
`/rabbit-cage-config display-timezone <value>` and consumed by contract's
`resolve_display_tz` (contract Inv 67). The entry is generic (no special-casing
in the command/script): it is dispatched by the SAME thin wrapper over
`config_dispatch` that handles every other rabbit-cage configurable.

  (i)   the entry exists with id == "display-timezone".
  (ii)  subcommand == "display-timezone" and command == "rabbit-cage-config".
  (iii) json-key storage at settings.local.json, key env.RABBIT_DISPLAY_TIMEZONE.
  (iv)  default == "local".
  (v)   it is a free scalar — declares no strict `values` enum (set-time
        validation is unnecessary: contract degrades an invalid value to local
        at READ time per Inv 67), and dispatches via an actions block.
  (vi)  end-to-end round-trip: setting the value writes
        env.RABBIT_DISPLAY_TIMEZONE and contract.resolve_display_tz reads it
        back (UTC -> datetime.timezone.utc); the default resolves to local.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the per-feature config command is superseded by a
    native rabbit CLI configuration mechanism.
"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CAGE = REPO / ".claude/features/rabbit-cage"
CAGE_FJ = CAGE / "feature.json"
SCRIPT = CAGE / "scripts/rabbit-cage-config.py"
CONTRACT = REPO / ".claude/features/contract"

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


def _entry():
    data = json.loads(CAGE_FJ.read_text())
    for c in data.get("configuration", []):
        if c.get("id") == "display-timezone":
            return c
    return None


def _make_temp_repo(tmp):
    feats = Path(tmp) / ".claude" / "features"
    (feats / "rabbit-cage").mkdir(parents=True)
    (feats / "rabbit-cage" / "feature.json").write_text(CAGE_FJ.read_text())
    os.symlink(CONTRACT, feats / "contract")
    return tmp


def _run(tmp, *args):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = str(tmp)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env,
    )


def main() -> int:
    cfg = _entry()
    if cfg is None:
        ko("no display-timezone entry in configuration[]")
        print()
        print(f"summary: {PASS} passed, {FAIL} failed")
        return 1
    ok("display-timezone entry present in configuration[]")

    # (ii) subcommand + command.
    if cfg.get("subcommand") == "display-timezone":
        ok("subcommand == display-timezone")
    else:
        ko(f"subcommand != display-timezone: {cfg.get('subcommand')!r}")
    if cfg.get("command") == "rabbit-cage-config":
        ok("command == rabbit-cage-config")
    else:
        ko(f"command != rabbit-cage-config: {cfg.get('command')!r}")

    # (iii) json-key storage shape.
    storage = cfg.get("storage") or {}
    if storage.get("type") == "json-key":
        ok("storage.type == json-key")
    else:
        ko(f"storage.type != json-key: {storage.get('type')!r}")
    if storage.get("file") == ".claude/settings.local.json":
        ok("storage.file == .claude/settings.local.json")
    else:
        ko(f"storage.file != settings.local.json: {storage.get('file')!r}")
    if storage.get("key") == "env.RABBIT_DISPLAY_TIMEZONE":
        ok("storage.key == env.RABBIT_DISPLAY_TIMEZONE")
    else:
        ko(f"storage.key != env.RABBIT_DISPLAY_TIMEZONE: {storage.get('key')!r}")

    # (iv) default.
    if cfg.get("default") == "local":
        ok("default == local")
    else:
        ko(f"default != local: {cfg.get('default')!r}")

    # (v) free scalar — no strict values enum; dispatches via actions.
    if not cfg.get("values"):
        ok("declares no strict values enum (free scalar)")
    else:
        ko(f"unexpected strict values enum: {cfg.get('values')!r}")
    if cfg.get("actions"):
        ok("declares an actions block (generic dispatch)")
    else:
        ko("declares no actions block — cannot dispatch a free scalar")

    # (vi) end-to-end round-trip through the real script + contract resolver.
    if SCRIPT.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            _make_temp_repo(tmp)
            action = next(iter((cfg.get("actions") or {}).keys()), None)
            r = _run(tmp, "display-timezone", action, "UTC")
            slj = Path(tmp) / ".claude" / "settings.local.json"
            wrote = ""
            if slj.is_file():
                data = json.loads(slj.read_text())
                wrote = data.get("env", {}).get("RABBIT_DISPLAY_TIMEZONE", "")
            if r.returncode == 0 and wrote == "UTC":
                ok("display-timezone <action> UTC writes env.RABBIT_DISPLAY_TIMEZONE=UTC")
            else:
                ko(f"set UTC failed: rc={r.returncode} wrote={wrote!r} err={r.stderr}")

            # contract.resolve_display_tz reads the written value back as UTC.
            sys.path.insert(0, str(CONTRACT))
            try:
                from lib.runtime import resolve_display_tz  # noqa: PLC0415
            finally:
                pass
            tz = resolve_display_tz(str(tmp))
            if tz == datetime.timezone.utc:
                ok("resolve_display_tz reads the stored UTC value back")
            else:
                ko(f"resolve_display_tz did not return UTC: {tz!r}")

        # default (no value stored) resolves to local.
        with tempfile.TemporaryDirectory() as tmp2:
            _make_temp_repo(tmp2)
            local = datetime.datetime.now().astimezone().tzinfo
            tz = resolve_display_tz(str(tmp2))
            if tz == local:
                ok("default (no stored value) resolves to local")
            else:
                ko(f"default did not resolve to local: {tz!r} != {local!r}")
    else:
        ko(f"script missing: {SCRIPT}")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
