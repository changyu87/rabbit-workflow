#!/usr/bin/env python3
"""test-rabbit-cage-config-command.py — spec Inv 40.

Exercises the per-feature config command /rabbit-cage-config (phase 3 of #733):

  (i)   scope-guard on round-trips the .rabbit-scope-override marker (no restart
        prompt).
  (ii)  bypass-permissions true writes permissions.defaultMode=bypassPermissions
        to settings.local.json AND emits the restart prompt.
  (iii) bash-allow add npm appends Bash(npm:*) to permissions.allow.
  (iv)  unknown subcommand / value exits non-zero.
  (v)   the backing script is a THIN wrapper — it imports dispatch_config and
        does NOT redefine the interpreter (_apply_template / _validate).
  (vi)  the six owned configurables declare command == "rabbit-cage-config"
        (tdd-autonomous is relocated out of rabbit-cage per #733 phase 3;
        display-timezone is the sixth owned configurable per #1011).
  (vii) the retired central rabbit-config interpreter is absent — the
        per-feature command is the sole config surface.
  (viii)the command frontmatter carries the six required keys and the manifest
        registers it.
  (ix)  FEATURE_INCLUDES / COMMANDS list the command + script + config_dispatch.py.

The mutation tests run the REAL script as a subprocess against a temp repo
whose RABBIT_ROOT carries a real-shaped rabbit-cage feature.json and a symlink
to the live contract feature (so the thin wrapper's import resolves).

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the per-feature config command is superseded by a
    native rabbit CLI configuration mechanism.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CAGE = REPO / ".claude/features/rabbit-cage"
CAGE_FJ = CAGE / "feature.json"
SCRIPT = CAGE / "scripts/rabbit-cage-config.py"
COMMAND_MD = CAGE / "commands/rabbit-cage-config.md"
INSTALL_PY = CAGE / "install.py"
CONTRACT = REPO / ".claude/features/contract"
RABBIT_CONFIG = (REPO
                 / ".claude/features/rabbit-config"
                 / "skills/rabbit-config/scripts/rabbit-config.py")

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


def _make_temp_repo(tmp):
    """Build a minimal repo tree at tmp: rabbit-cage feature.json (the live
    one) + a symlink to the live contract feature, so the thin wrapper's
    `from lib.config_dispatch import dispatch_config` resolves against
    <RABBIT_ROOT>/.claude/features/contract."""
    feats = Path(tmp) / ".claude" / "features"
    (feats / "rabbit-cage").mkdir(parents=True)
    # Copy the live rabbit-cage feature.json (the configuration[] under test).
    (feats / "rabbit-cage" / "feature.json").write_text(CAGE_FJ.read_text())
    # Symlink the contract feature so contract.lib.* import resolves.
    os.symlink(CONTRACT, feats / "contract")
    return tmp


def _run(tmp, *args):
    env = dict(os.environ)
    env["RABBIT_ROOT"] = str(tmp)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env,
    )


def config_for(tmp, cid):
    """Return the configuration[] entry with id == cid from the temp repo's
    copy of rabbit-cage's feature.json."""
    fj = Path(tmp) / ".claude" / "features" / "rabbit-cage" / "feature.json"
    data = json.loads(fj.read_text())
    for c in data.get("configuration", []):
        if c.get("id") == cid:
            return c
    return {}


def main() -> int:
    # ---- (v) thin-wrapper: imports dispatch_config, no re-implemented interp.
    if not SCRIPT.is_file():
        ko(f"script missing: {SCRIPT}")
    else:
        body = SCRIPT.read_text()
        if "dispatch_config" in body and "config_dispatch" in body:
            ok("script imports the shared dispatch_config helper")
        else:
            ko("script does not import dispatch_config / config_dispatch")
        # No re-implemented interpreter internals.
        if "def _apply_template" in body or "def _validate" in body:
            ko("script re-implements interpreter internals (_apply_template/_validate)")
        else:
            ok("script does not re-implement the interpreter (thin wrapper)")

    # ---- mutation round-trips via the real script subprocess.
    if SCRIPT.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            _make_temp_repo(tmp)

            # (i) scope-guard on: idempotent delete_marker, no restart prompt.
            override = Path(tmp) / ".rabbit-scope-override"
            override.write_text("session")
            r = _run(tmp, "scope-guard", "on")
            if r.returncode == 0 and not override.exists():
                ok("scope-guard on deletes .rabbit-scope-override")
            else:
                ko(f"scope-guard on failed: rc={r.returncode} "
                   f"exists={override.exists()} err={r.stderr}")
            if "restart Claude" not in (r.stdout + r.stderr):
                ok("scope-guard on emits no restart prompt")
            else:
                ko("scope-guard on unexpectedly emitted a restart prompt")

            # (ii) bypass-permissions true -> settings.local.json + restart prompt.
            r = _run(tmp, "bypass-permissions", "true")
            slj = Path(tmp) / ".claude" / "settings.local.json"
            wrote = False
            if slj.is_file():
                data = json.loads(slj.read_text())
                wrote = (data.get("permissions", {}).get("defaultMode")
                         == "bypassPermissions")
            if r.returncode == 0 and wrote:
                ok("bypass-permissions true writes permissions.defaultMode")
            else:
                ko(f"bypass-permissions true failed: rc={r.returncode} "
                   f"wrote={wrote} err={r.stderr}")
            if "restart Claude" in (r.stdout + r.stderr):
                ok("bypass-permissions true emits the restart prompt")
            else:
                ko(f"bypass-permissions true missing restart prompt: "
                   f"out={r.stdout!r} err={r.stderr!r}")

            # (iii) bash-allow add npm -> Bash(npm:*) in permissions.allow.
            r = _run(tmp, "bash-allow", "add", "npm")
            allow = []
            if slj.is_file():
                allow = json.loads(slj.read_text()).get(
                    "permissions", {}).get("allow", [])
            if r.returncode == 0 and "Bash(npm:*)" in allow:
                ok("bash-allow add npm appends Bash(npm:*)")
            else:
                ko(f"bash-allow add npm failed: rc={r.returncode} "
                   f"allow={allow} err={r.stderr}")

            # (display-timezone round-trip, #1011) — the SAME thin wrapper
            # dispatches the free-scalar display-timezone with no special-casing.
            dt_cfg = config_for(tmp, "display-timezone")
            dt_action = next(iter((dt_cfg.get("actions") or {}).keys()), None)
            r = _run(tmp, "display-timezone", dt_action, "UTC")
            wrote_tz = ""
            if slj.is_file():
                wrote_tz = json.loads(slj.read_text()).get(
                    "env", {}).get("RABBIT_DISPLAY_TIMEZONE", "")
            if r.returncode == 0 and wrote_tz == "UTC":
                ok("display-timezone set UTC writes env.RABBIT_DISPLAY_TIMEZONE=UTC")
            else:
                ko(f"display-timezone set UTC failed: rc={r.returncode} "
                   f"wrote={wrote_tz!r} err={r.stderr}")
            # default resolves to local (no value stored before the set above —
            # asserted via the configurable default declaration).
            if dt_cfg.get("default") == "local":
                ok("display-timezone default resolves to local")
            else:
                ko(f"display-timezone default != local: {dt_cfg.get('default')!r}")

            # (iv) unknown subcommand / value exit non-zero.
            r = _run(tmp, "no-such-sub")
            if r.returncode != 0:
                ok("unknown subcommand exits non-zero")
            else:
                ko("unknown subcommand unexpectedly exited 0")
            r = _run(tmp, "scope-guard", "bogus")
            if r.returncode != 0:
                ok("unknown value exits non-zero")
            else:
                ko("unknown value unexpectedly exited 0")

    # ---- (vii) the central rabbit-config interpreter is retired: absent.
    if not RABBIT_CONFIG.exists():
        ok("central rabbit-config interpreter absent (retired)")
    else:
        ko(f"central rabbit-config interpreter still present: {RABBIT_CONFIG}")

    # ---- declaration assertions on the live feature.json.
    data = json.loads(CAGE_FJ.read_text())
    config = {c["id"]: c for c in data.get("configuration", [])}
    owned = ("scope-guard", "bypass-permissions", "allowed-tools",
             "bash-allow", "prompt-threshold", "display-timezone")
    # (vi) command field.
    for cid in owned:
        if config.get(cid, {}).get("command") == "rabbit-cage-config":
            ok(f"{cid} declares command == rabbit-cage-config")
        else:
            ko(f"{cid} missing command == rabbit-cage-config: "
               f"{config.get(cid, {}).get('command')!r}")
    if "tdd-autonomous" not in config:
        ok("tdd-autonomous not declared in rabbit-cage (relocated, #733 ph3)")
    else:
        ko("tdd-autonomous unexpectedly still declared in rabbit-cage")

    # (viii) command frontmatter + manifest registration.
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
           and e.get("args", {}).get("source") == "commands/rabbit-cage-config.md"
           for e in manifest):
        ok("manifest registers commands/rabbit-cage-config.md")
    else:
        ko("manifest does not register commands/rabbit-cage-config.md")

    # (ix) install.py closure.
    install_src = INSTALL_PY.read_text()
    for needle, label in (
        ("commands/rabbit-cage-config.md", "FEATURE_INCLUDES command"),
        ("scripts/rabbit-cage-config.py", "FEATURE_INCLUDES script"),
        ("lib/config_dispatch.py", "FEATURE_INCLUDES contract config_dispatch"),
        (".claude/commands/rabbit-cage-config.md", "COMMANDS tuple"),
    ):
        if needle in install_src:
            ok(f"install.py lists {label}")
        else:
            ko(f"install.py missing {label} ({needle})")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
