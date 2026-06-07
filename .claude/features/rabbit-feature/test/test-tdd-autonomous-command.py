#!/usr/bin/env python3
"""test-tdd-autonomous-command.py — Inv 58 (e2e).

Exercises the per-feature config command /rabbit-tdd-autonomous (phase 3 of
#733). The command is a THIN wrapper over contract.lib.config_dispatch:

  (i)   tdd-autonomous true writes the .rabbit-tdd-autonomous bypass marker AND
        emits the branded restart prompt (restart_required).
  (ii)  tdd-autonomous false deletes the marker (gate active) — round-trip.
  (iii) unknown subcommand / value exits non-zero.
  (iv)  the backing script is a THIN wrapper: it imports dispatch_config and
        does NOT re-implement the interpreter (_apply_template / _validate).
  (v)   the command frontmatter carries the six required keys and the manifest
        registers commands/rabbit-tdd-autonomous.md via publish_command.

/rabbit-tdd-autonomous is the SOLE supported surface for this configurable: the
historical central /rabbit-config tdd-autonomous coexistence window has ended
ahead of rabbit-config's retirement (#769), so this test no longer asserts the
rabbit-config interpreter.

The mutation tests run the REAL script as a subprocess against a temp repo whose
RABBIT_ROOT carries the live rabbit-feature feature.json and a symlink to the
live contract feature (so the thin wrapper's import resolves).

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the per-feature config command is superseded by a
    native rabbit CLI configuration mechanism.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FEATURE = REPO / ".claude/features/rabbit-feature"
FEATURE_FJ = FEATURE / "feature.json"
SCRIPT = FEATURE / "scripts/rabbit-tdd-autonomous-config.py"
COMMAND_MD = FEATURE / "commands/rabbit-tdd-autonomous.md"
CONTRACT = REPO / ".claude/features/contract"

MARKER = ".rabbit-tdd-autonomous"

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


def _make_temp_repo(tmp: str) -> None:
    """rabbit-feature feature.json (live) + symlink to live contract feature so
    `from lib.config_dispatch import dispatch_config` resolves against
    <RABBIT_ROOT>/.claude/features/contract."""
    feats = Path(tmp) / ".claude" / "features"
    (feats / "rabbit-feature").mkdir(parents=True)
    (feats / "rabbit-feature" / "feature.json").write_text(FEATURE_FJ.read_text())
    os.symlink(CONTRACT, feats / "contract")


def _run(tmp: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["RABBIT_ROOT"] = str(tmp)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env,
    )


def main() -> int:
    # ---- (iv) thin-wrapper: imports dispatch_config, no re-implemented interp.
    if not SCRIPT.is_file():
        ko(f"script missing: {SCRIPT}")
    else:
        body = SCRIPT.read_text()
        if "dispatch_config" in body and "config_dispatch" in body:
            ok("script imports the shared dispatch_config helper")
        else:
            ko("script does not import dispatch_config / config_dispatch")
        if "def _apply_template" in body or "def _validate" in body:
            ko("script re-implements interpreter internals")
        else:
            ok("script does not re-implement the interpreter (thin wrapper)")

    # ---- mutation round-trips via the real script subprocess.
    if SCRIPT.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            _make_temp_repo(tmp)
            marker = Path(tmp) / MARKER

            # (i) true writes the bypass marker + restart prompt.
            r = _run(tmp, "tdd-autonomous", "true")
            if r.returncode == 0 and marker.exists():
                ok(f"tdd-autonomous true writes {MARKER}")
            else:
                ko(f"tdd-autonomous true failed: rc={r.returncode} "
                   f"exists={marker.exists()} err={r.stderr}")
            if "restart Claude" in (r.stdout + r.stderr):
                ok("tdd-autonomous true emits the restart prompt")
            else:
                ko(f"tdd-autonomous true missing restart prompt: "
                   f"out={r.stdout!r} err={r.stderr!r}")

            # (ii) false deletes the marker (gate active) — round-trip.
            r = _run(tmp, "tdd-autonomous", "false")
            if r.returncode == 0 and not marker.exists():
                ok(f"tdd-autonomous false deletes {MARKER}")
            else:
                ko(f"tdd-autonomous false failed: rc={r.returncode} "
                   f"exists={marker.exists()} err={r.stderr}")

            # (iii) unknown subcommand / value exit non-zero.
            r = _run(tmp, "no-such-sub")
            if r.returncode != 0:
                ok("unknown subcommand exits non-zero")
            else:
                ko("unknown subcommand unexpectedly exited 0")
            r = _run(tmp, "tdd-autonomous", "bogus")
            if r.returncode != 0:
                ok("unknown value exits non-zero")
            else:
                ko("unknown value unexpectedly exited 0")

    # ---- (v) command frontmatter + manifest registration.
    data = json.loads(FEATURE_FJ.read_text())
    if COMMAND_MD.is_file():
        md = COMMAND_MD.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", md, re.DOTALL)
        if m:
            fm = m.group(1)
            required = ("name", "description", "version", "owner",
                        "deprecation_criterion", "template_version")
            missing = [k for k in required if not re.search(rf"^{k}:\s*\S", fm, re.M)]
            if not missing:
                ok("command frontmatter carries all six required keys")
            else:
                ko(f"command frontmatter missing keys: {missing}")
            if re.search(r"^owner:\s*rabbit-workflow team\s*$", fm, re.M):
                ok("command owner is 'rabbit-workflow team'")
            else:
                ko("command owner is not exactly 'rabbit-workflow team'")
        else:
            ko("command file has no YAML frontmatter block")
    else:
        ko(f"command file missing: {COMMAND_MD}")

    manifest = data.get("manifest", [])
    if any(e.get("api") == "publish_command"
           and e.get("args", {}).get("source") == "commands/rabbit-tdd-autonomous.md"
           for e in manifest):
        ok("manifest registers commands/rabbit-tdd-autonomous.md via publish_command")
    else:
        ko("manifest does not register commands/rabbit-tdd-autonomous.md")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
