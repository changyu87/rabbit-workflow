#!/usr/bin/env python3
"""test-bypass-permissions-per-feature-alert.py — issue #780.

Re-home of the bypass-permissions active-override alert as a PER-FEATURE
`runtime[]` entry (retire-rabbit-config step 1 of #769). Spec Inv 40(c).

Pins the two halves of #780:

  A. Declaration. rabbit-cage's feature.json declares an
     `emit_configurable_alert` entry resolving
     feature_name == "rabbit-cage" + configurable_id == "bypass-permissions"
     in BOTH runtime.Stop and runtime.SessionStart.

  B. Behaviour (e2e against the live contract.lib.runtime). With the
     declared args, emit_configurable_alert:
       - FIRES (returns the inlined-revoke alert-message print_result) when
         permissions.defaultMode == "bypassPermissions" in
         .claude/settings.local.json (post-#775 polarity);
       - is silent (ok_result) when the override is absent.

  C. install.py no longer ships rabbit-config (FEATURE_INCLUDES key removed
     AND the SAME_PATH/SKILLS rabbit-config skill-copy tuple removed).

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the bypass-permissions configurable is retired
or contract Inv 40 changes the per-feature alert ownership model.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]
CAGE_FJ = CAGE / "feature.json"
REPO = Path(__file__).resolve().parents[4]
INSTALL_PY = CAGE / "install.py"

# Allow `from contract.lib import runtime` from the live tree.
sys.path.insert(0, str(REPO / ".claude/features"))

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
    print(f"  PASS {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


def _bypass_runtime_entry(entries):
    """Return the emit_configurable_alert entry resolving rabbit-cage's
    bypass-permissions configurable, or None."""
    for e in entries or []:
        if e.get("api") != "emit_configurable_alert":
            continue
        args = e.get("args") or {}
        if (args.get("feature_name") == "rabbit-cage"
                and args.get("configurable_id") == "bypass-permissions"):
            return e
    return None


def load_install_module():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    data = json.loads(CAGE_FJ.read_text())
    runtime_decls = data.get("runtime") or {}

    # A. Declaration in both Stop and SessionStart.
    for event in ("Stop", "SessionStart"):
        entry = _bypass_runtime_entry(runtime_decls.get(event))
        if entry is not None:
            ok(f"runtime.{event} declares bypass-permissions emit_configurable_alert")
        else:
            ko(f"runtime.{event} missing bypass-permissions emit_configurable_alert entry")

    # B. Behaviour — fires on active marker state, silent when absent.
    from contract.lib import runtime  # type: ignore

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cage_dir = root / ".claude/features/rabbit-cage"
        cage_dir.mkdir(parents=True)
        # Copy the live feature.json so the configurable definition is real.
        (cage_dir / "feature.json").write_text(CAGE_FJ.read_text())

        # B1 — override absent -> ok_result (silent).
        res = runtime.emit_configurable_alert(
            "rabbit-cage", "bypass-permissions", repo_root=str(root))
        if res.get("type") == "ok":
            ok("emit_configurable_alert silent (ok) when override absent")
        else:
            ko(f"expected ok_result with no override, got {res!r}")

        # B2 — override active -> fires the inlined-revoke alert.
        settings = root / ".claude/settings.local.json"
        settings.write_text(json.dumps(
            {"permissions": {"defaultMode": "bypassPermissions"}}))
        res = runtime.emit_configurable_alert(
            "rabbit-cage", "bypass-permissions", repo_root=str(root))
        if res.get("type") == "print":
            ok("emit_configurable_alert FIRES (print) when override active")
        else:
            ko(f"expected print_result with override active, got {res!r}")
        if res.get("text") == EXPECTED_TEXT:
            ok("alert text is the inlined-revoke form")
        else:
            ko(f"alert text mismatch: {res.get('text')!r} != {EXPECTED_TEXT!r}")
        if res.get("icon") == EXPECTED_ICON:
            ok("alert icon is siren glyph")
        else:
            ko(f"alert icon mismatch: {res.get('icon')!r}")
        if res.get("color") == EXPECTED_COLOR:
            ok("alert color is red")
        else:
            ko(f"alert color mismatch: {res.get('color')!r}")

    # C. install.py no longer ships rabbit-config.
    mod = load_install_module()
    includes = getattr(mod, "FEATURE_INCLUDES", {})
    if "rabbit-config" not in includes:
        ok("install.py FEATURE_INCLUDES no longer has 'rabbit-config' key")
    else:
        ko("install.py FEATURE_INCLUDES still carries 'rabbit-config' key")

    skills = getattr(mod, "SKILLS", [])
    rc_skill_src = ".claude/features/rabbit-config/skills/rabbit-config/SKILL.md"
    if not any(src == rc_skill_src for src, _dst in skills):
        ok("install.py SKILLS no longer copies the rabbit-config skill")
    else:
        ko("install.py SKILLS still copies the rabbit-config skill")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
