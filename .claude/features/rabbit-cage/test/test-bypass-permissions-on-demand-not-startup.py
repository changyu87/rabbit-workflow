#!/usr/bin/env python3
"""test-bypass-permissions-on-demand-not-startup.py — issue #914.

The permission-bypass info message used to be advertised as an always-loaded
SessionStart welcome subline (issue #889). On a fresh `.rabbit` install it
printed on EVERY startup. That information is useful but should be shown
ONLY when explicitly queried, not on every session start.

This test asserts the post-#914 contract:

  A. The SessionStart `welcome_with_policy` entry carries NO permission-bypass
     info subline — the always-on startup advertisement is gone. The three
     policy-summary sublines remain.
  B. The permission-bypass info message IS emitted ON-DEMAND by the
     `/rabbit-cage-config` query path (`rabbit-cage-config.py help`), preserving
     the message content/branding (the `Shift+Tab` ephemeral toggle AND the
     persisted `/rabbit-cage-config bypass-permissions true|false` path that
     writes `defaultMode` and takes effect after a Claude relaunch).
  C. End-to-end regression (do NOT regress #917): when a `session`
     scope-override marker is active, the SessionStart safety notice
     `SCOPE GUARD OFF (session override active)` STILL fires on startup. That
     scope-override notice is a SAFETY alert and is distinct from the
     permission-bypass info message; #914 changes ONLY the latter.

Drives the REAL deployed session-start-dispatcher subprocess and the REAL
rabbit-cage-config.py subprocess against faithful install roots.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the bypass-permissions configurable is retired or
    the on-demand config-query surface is superseded by a native rabbit CLI.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RABBIT_CAGE = REPO / ".claude/features/rabbit-cage"
SESSION_SRC = RABBIT_CAGE / "hooks/session-start-dispatcher.py"
DISPATCHER_LIB_SRC = RABBIT_CAGE / "hooks/_dispatcher_lib.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"
CONFIG_SCRIPT = RABBIT_CAGE / "scripts/rabbit-cage-config.py"
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


def _build_install_root(td: Path) -> Path:
    install_root = td / "rabbit_install"
    install_root.mkdir()

    hooks_dir = install_root / ".claude/hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy2(SESSION_SRC, hooks_dir / "session-start-dispatcher.py")
    shutil.copy2(DISPATCHER_LIB_SRC, hooks_dir / "_dispatcher_lib.py")

    (install_root / ".claude/features").mkdir(parents=True, exist_ok=True)
    shutil.copytree(CONTRACT, install_root / ".claude/features/contract")
    shutil.copytree(
        REPO / ".claude/features/rabbit-meta",
        install_root / ".claude/features/rabbit-meta",
    )
    cage_dir = install_root / ".claude/features/rabbit-cage"
    cage_dir.mkdir(parents=True)
    shutil.copy2(RABBIT_CAGE_FEATURE_JSON, cage_dir / "feature.json")
    pol = install_root / ".claude/features/policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("# stub\n")
    (pol / "spec-rules.md").write_text("# stub\n")
    (pol / "coding-rules.md").write_text("# stub\n")

    (install_root / ".version").write_text("v9.9.9\n")
    return install_root


def _run_session_start(install_root: Path) -> subprocess.CompletedProcess:
    dispatcher = install_root / ".claude/hooks/session-start-dispatcher.py"
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="", capture_output=True, text=True,
        env=env, cwd=str(install_root),
    )


def _system_message(stdout: str) -> str:
    stdout = stdout.strip()
    assert stdout, "expected JSON on stdout"
    return json.loads(stdout).get("systemMessage", "")


def main() -> int:
    # ---- A. The SessionStart welcome carries NO permission-bypass subline.
    data = json.loads(RABBIT_CAGE_FEATURE_JSON.read_text())
    ss = data.get("runtime", {}).get("SessionStart", [])
    welcome = next(
        (e for e in ss if e.get("api") == "welcome_with_policy"), None)
    if welcome is None:
        ko("runtime.SessionStart has no welcome_with_policy entry")
        print()
        print(f"summary: {PASS} passed, {FAIL} failed")
        return 1

    sublines = welcome.get("args", {}).get("sublines", [])
    subline_texts = [sl.get("text", "") for sl in sublines]
    bypass_subline = next(
        (t for t in subline_texts
         if "bypass-permissions" in t or "Shift+Tab" in t), None)
    if bypass_subline is None:
        ok("welcome carries NO permission-bypass startup subline")
    else:
        ko(f"welcome still advertises permission bypass on startup: {bypass_subline!r}")

    for needle in ("philosophy.md", "spec-rules.md", "coding-rules.md"):
        if any(needle in t for t in subline_texts):
            ok(f"policy subline {needle} preserved")
        else:
            ko(f"policy subline {needle} missing (regression)")

    # End-to-end: the real deployed dispatcher renders NO bypass advert.
    with tempfile.TemporaryDirectory() as td:
        install_root = _build_install_root(Path(td).resolve())
        proc = _run_session_start(install_root)
        if proc.returncode != 0:
            ko(f"session-start-dispatcher failed: stderr={proc.stderr!r}")
        else:
            ok("session-start-dispatcher exited 0")
            sysmsg = _system_message(proc.stdout)
            if "/rabbit-cage-config bypass-permissions" not in sysmsg and \
                    "Shift+Tab" not in sysmsg:
                ok("rendered SessionStart carries no permission-bypass advert")
            else:
                ko("rendered SessionStart still advertises permission bypass")
            for needle in ("philosophy.md", "spec-rules.md", "coding-rules.md"):
                if needle in sysmsg:
                    ok(f"rendered policy subline {needle} present")
                else:
                    ko(f"rendered policy subline {needle} missing (regression)")

    # ---- B. The message IS available ON-DEMAND via the config-query path.
    r = subprocess.run(
        [sys.executable, str(CONFIG_SCRIPT), "help"],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    if r.returncode == 0:
        ok("rabbit-cage-config help exits 0")
    else:
        ko(f"rabbit-cage-config help exit non-zero: rc={r.returncode}")
    if "/rabbit-cage-config bypass-permissions" in out:
        ok("on-demand help surfaces the persisted bypass-permissions path")
    else:
        ko("on-demand help missing the persisted bypass-permissions path")
    if "Shift+Tab" in out:
        ok("on-demand help names the ephemeral Shift+Tab live toggle")
    else:
        ko("on-demand help missing the Shift+Tab live toggle")
    if re.search(r"relaunch|restart", out, re.I):
        ok("on-demand help notes the persisted path is relaunch-required")
    else:
        ko("on-demand help does not note relaunch requirement")

    # ---- C. Regression (#917): scope-override SAFETY notice still fires.
    with tempfile.TemporaryDirectory() as td:
        install_root = _build_install_root(Path(td).resolve())
        # Plugin-mode canonical session-override marker (Inv 25).
        rabbit_dir = install_root / ".rabbit"
        rabbit_dir.mkdir(parents=True, exist_ok=True)
        (rabbit_dir / ".rabbit-scope-override").write_text("session")
        # Standalone canonical location too (belt-and-suspenders for the
        # repo_root the dispatcher resolves).
        (install_root / ".rabbit-scope-override").write_text("session")
        proc = _run_session_start(install_root)
        if proc.returncode != 0:
            ko(f"session-start (override active) failed: {proc.stderr!r}")
        else:
            sysmsg = _system_message(proc.stdout)
            if "SCOPE GUARD OFF" in sysmsg:
                ok("scope-override SAFETY notice STILL fires at startup (#917 intact)")
            else:
                ko("scope-override SAFETY notice missing — #917 regressed")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
