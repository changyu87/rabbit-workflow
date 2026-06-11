#!/usr/bin/env python3
"""test-restart-advisory-tiered-by-change-type.py — e2e: issue #1156 (Inv 54e).

The mid-session restart advisory (Inv 54) must TIER its remedy by change type
rather than always recommending a full restart. Since Claude Code v2.1.152,
`/reload-skills` reloads `SKILL.md` definitions mid-session WITHOUT a restart,
and skill `scripts/` are re-read on every invocation. So the re-check
classifies the SET of changed restart-sensitive paths and emits the CHEAPEST
sufficient remedy:

  - ONLY `.claude/skills/**/SKILL.md` changed → a `/reload-skills` advisory
    (`reload ADVISED (not required): ... run /reload-skills ...`), NOT the
    full-restart advisory.
  - ONLY skill `scripts/` changed → NOTHING (re-read on next call).
  - any hook / `CLAUDE.md` / settings / `.claude/agents/**` change → the
    full-restart advisory (`restart ADVISED ...`), unchanged.
  - MIXED → the superset wins (strict precedence full-restart >
    reload-skills > nothing).

This is an end-to-end test: it builds a fake install root with the deployed
dispatchers + shared lib, runs SessionStart to snapshot, mutates surfaces on
disk, runs the Stop and UserPromptSubmit dispatchers as subprocesses, and
asserts on the emitted JSON.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RABBIT_CAGE = REPO / ".claude/features/rabbit-cage"
STOP_SRC = RABBIT_CAGE / "hooks/stop-dispatcher.py"
SESSION_SRC = RABBIT_CAGE / "hooks/session-start-dispatcher.py"
UPS_SRC = RABBIT_CAGE / "hooks/user-prompt-submit-dispatcher.py"
DISPATCHER_LIB_SRC = RABBIT_CAGE / "hooks/_dispatcher_lib.py"
SNAPSHOT_SRC = RABBIT_CAGE / "hooks/restart_snapshot.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"

# Tier fragments.
RESTART_FRAGMENT = "restart ADVISED"
RELOAD_FRAGMENT = "reload ADVISED"
RELOAD_COMMAND = "/reload-skills"
SNAPSHOT_FILE = ".rabbit-restart-snapshot"

pass_n = 0
fail_n = 0


def ok(msg):
    global pass_n
    print(f"  PASS: {msg}")
    pass_n += 1


def bad(msg):
    global fail_n
    print(f"  FAIL: {msg}")
    fail_n += 1


def _build_install_root(td: Path) -> Path:
    install_root = td / "rabbit_install"
    install_root.mkdir()

    hooks_dir = install_root / ".claude/hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy2(STOP_SRC, hooks_dir / "stop-dispatcher.py")
    shutil.copy2(SESSION_SRC, hooks_dir / "session-start-dispatcher.py")
    shutil.copy2(UPS_SRC, hooks_dir / "user-prompt-submit-dispatcher.py")
    shutil.copy2(DISPATCHER_LIB_SRC, hooks_dir / "_dispatcher_lib.py")
    shutil.copy2(SNAPSHOT_SRC, hooks_dir / "restart_snapshot.py")

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

    # Restart-sensitive surfaces seeded with an ORIGINAL (loaded) version.
    (install_root / "CLAUDE.md").write_text("# original claude md\n")
    (install_root / ".claude/settings.json").write_text('{"orig": 1}\n')
    skill_dir = install_root / ".claude/skills/rabbit-feature-touch"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# original skill v1\n")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts/helper.py").write_text("# original helper v1\n")
    agents_dir = install_root / ".claude/agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "tdd-subagent.md").write_text("# original agent v1\n")

    return install_root


def _run(dispatcher: Path, install_root: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(install_root),
    )


def _stop(r):
    return _run(r / ".claude/hooks/stop-dispatcher.py", r)


def _session(r):
    return _run(r / ".claude/hooks/session-start-dispatcher.py", r)


def _ups(r):
    return _run(r / ".claude/hooks/user-prompt-submit-dispatcher.py", r)


def _sysmsg(proc) -> str:
    out = proc.stdout.strip()
    if not out:
        return ""
    try:
        return json.loads(out).get("systemMessage", "")
    except (json.JSONDecodeError, ValueError):
        return ""


def _snapshot_session(r):
    proc = _session(r)
    assert proc.returncode == 0, f"session failed: {proc.stderr!r}"
    assert (r / SNAPSHOT_FILE).exists(), "SessionStart must write snapshot"


def _check_both(r, label, want_reload, want_restart):
    """Run Stop + UserPromptSubmit; assert presence/absence of each advisory."""
    for name, proc in (("Stop", _stop(r)), ("UserPromptSubmit", _ups(r))):
        if proc.returncode != 0:
            bad(f"[{label}] {name} non-zero rc={proc.returncode} "
                f"stderr={proc.stderr.strip()!r}")
            continue
        msg = _sysmsg(proc)
        has_reload = RELOAD_FRAGMENT in msg and RELOAD_COMMAND in msg
        # full-restart advisory: "restart ADVISED" but NOT the reload phrasing.
        has_restart = RESTART_FRAGMENT in msg
        if want_reload and not has_reload:
            bad(f"[{label}] {name} expected /reload-skills advisory; "
                f"sysmsg={msg!r}")
            continue
        if not want_reload and has_reload:
            bad(f"[{label}] {name} unexpected /reload-skills advisory; "
                f"sysmsg={msg!r}")
            continue
        if want_restart and not has_restart:
            bad(f"[{label}] {name} expected full-restart advisory; "
                f"sysmsg={msg!r}")
            continue
        if not want_restart and has_restart:
            bad(f"[{label}] {name} unexpected full-restart advisory; "
                f"sysmsg={msg!r}")
            continue
        ok(f"[{label}] {name} tier correct "
           f"(reload={want_reload}, restart={want_restart})")


# --- t1: ONLY SKILL.md changed → /reload-skills, NOT full-restart. ----------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")
    _check_both(r, "SKILL.md-only", want_reload=True, want_restart=False)


# --- t2: ONLY skill scripts/ changed → NEITHER advisory. --------------------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/scripts/helper.py").write_text(
        "# CHANGED helper v2\n")
    _check_both(r, "skill-scripts-only", want_reload=False, want_restart=False)


# --- t3: a hook change → full-restart, NOT /reload-skills. -------------------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/hooks/some-hook.py").write_text("# CHANGED hook\n")
    _check_both(r, "hook", want_reload=False, want_restart=True)


# --- t4: a CLAUDE.md change → full-restart, NOT /reload-skills. --------------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / "CLAUDE.md").write_text("# CHANGED claude md\n")
    _check_both(r, "CLAUDE.md", want_reload=False, want_restart=True)


# --- t5: an agent change → full-restart, NOT /reload-skills. -----------------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/agents/tdd-subagent.md").write_text("# CHANGED agent v2\n")
    _check_both(r, "agent", want_reload=False, want_restart=True)


# --- t6: MIXED SKILL.md + hook → full-restart (superset wins). --------------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")
    (r / ".claude/hooks/some-hook.py").write_text("# CHANGED hook\n")
    _check_both(r, "mixed SKILL.md+hook", want_reload=False, want_restart=True)


# --- t7: MIXED SKILL.md + skill scripts/ → /reload-skills (superset wins). --
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")
    (r / ".claude/skills/rabbit-feature-touch/scripts/helper.py").write_text(
        "# CHANGED helper v2\n")
    _check_both(r, "mixed SKILL.md+scripts", want_reload=True,
                want_restart=False)


print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
