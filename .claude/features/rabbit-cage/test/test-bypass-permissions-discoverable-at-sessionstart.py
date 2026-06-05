#!/usr/bin/env python3
"""test-bypass-permissions-discoverable-at-sessionstart.py — issue #889.

The rabbit-native persisted permission-mode path (`/rabbit-cage-config
bypass-permissions true|false`, which writes `permissions.defaultMode`) was
undiscoverable: nothing in loaded context advertised it, so when a user
expressed permission-mode intent the dispatcher defaulted to upstream Claude
Code mechanisms (Shift+Tab, --dangerously-skip-permissions) and never surfaced
the rabbit-native path.

The bypass-permissions active-override alert (Inv 40c) only fires when bypass
is ALREADY active, so it cannot help discoverability when bypass is OFF. The
fix surfaces a concise, always-loaded SessionStart subline (a `welcome_with_policy`
subline entry in rabbit-cage's runtime.SessionStart) that advertises BOTH
mechanisms and their difference:

  1. Live session toggle (Shift+Tab) — ephemeral, current session, immediate.
  2. Persisted `/rabbit-cage-config bypass-permissions true` — writes
     `defaultMode`, takes effect after a Claude relaunch.

This test is end-to-end: it drives the REAL deployed session-start-dispatcher
subprocess against a faithful install root and asserts the rendered
systemMessage carries the discoverability subline.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when the bypass-permissions configurable is retired
or the SessionStart welcome surface stops carrying policy sublines.
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


def _build_install_root(td: Path) -> Path:
    install_root = td / "rabbit_install"
    install_root.mkdir()

    hooks_dir = install_root / ".claude/hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy2(SESSION_SRC, hooks_dir / "session-start-dispatcher.py")
    shutil.copy2(DISPATCHER_LIB_SRC, hooks_dir / "_dispatcher_lib.py")

    (install_root / ".claude/features").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REPO / ".claude/features/contract",
        install_root / ".claude/features/contract",
    )
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


def _run(install_root: Path) -> subprocess.CompletedProcess:
    dispatcher = install_root / ".claude/hooks/session-start-dispatcher.py"
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(install_root),
    )


def _system_message(stdout: str) -> str:
    stdout = stdout.strip()
    assert stdout, "expected JSON on stdout"
    return json.loads(stdout).get("systemMessage", "")


def main() -> int:
    # A. The feature.json declares a SessionStart welcome subline advertising
    #    the rabbit-native persisted permission-mode path.
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
    bypass_line = next(
        (t for t in subline_texts
         if "/rabbit-cage-config bypass-permissions" in t), None)
    if bypass_line is not None:
        ok("welcome subline advertises /rabbit-cage-config bypass-permissions")
    else:
        ko("no welcome subline mentions /rabbit-cage-config bypass-permissions")

    if bypass_line and "Shift+Tab" in bypass_line:
        ok("subline names the ephemeral Shift+Tab live toggle")
    else:
        ko("subline does not name the ephemeral Shift+Tab live toggle")

    if bypass_line and re.search(r"relaunch|restart", bypass_line, re.I):
        ok("subline notes the persisted path is relaunch-required")
    else:
        ko("subline does not note the persisted path is relaunch-required")

    # B. End-to-end: the real deployed dispatcher renders the subline.
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td).resolve()
        install_root = _build_install_root(td_path)
        proc = _run(install_root)
        if proc.returncode == 0:
            ok("session-start-dispatcher exited 0")
        else:
            ko(f"dispatcher failed: stderr={proc.stderr!r}")
            print()
            print(f"summary: {PASS} passed, {FAIL} failed")
            return 1

        sysmsg = _system_message(proc.stdout)
        if "/rabbit-cage-config bypass-permissions" in sysmsg:
            ok("rendered systemMessage carries the rabbit-native bypass path")
        else:
            ko("rendered systemMessage missing the rabbit-native bypass path")

        if "Shift+Tab" in sysmsg:
            ok("rendered systemMessage distinguishes the ephemeral Shift+Tab toggle")
        else:
            ko("rendered systemMessage missing the Shift+Tab distinction")

        # Regression: the three policy sublines remain present.
        for needle in ("philosophy.md", "spec-rules.md", "coding-rules.md"):
            if needle in sysmsg:
                ok(f"policy subline {needle} still present")
            else:
                ko(f"policy subline {needle} missing (regression)")

    print()
    print(f"summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
