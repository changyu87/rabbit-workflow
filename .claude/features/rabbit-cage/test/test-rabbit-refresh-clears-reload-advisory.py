#!/usr/bin/env python3
"""test-rabbit-refresh-clears-reload-advisory.py — e2e: issue #1193 (Inv 54f).

The tiered `reload ADVISED` advisory (Inv 54e) must be CLEARABLE by an action the
user can take mid-session WITHOUT a full restart. The #1173 wiring tied the clear
to the submitted prompt `/reload-skills`, but `/reload-skills` is a Claude Code
CLIENT-LOCAL built-in that reloads `SKILL.md` definitions in-process and NEVER
fires the UserPromptSubmit hook — so the dispatcher never observed it and
`rebaseline_skill_tier` was never called. The advisory persisted until a full
restart, the very thing it advised against.

The corrected clearing surface is the `/rabbit-refresh` command, which IS a real
submitted command whose body runs deterministic `!` bash. Its body now invokes
`scripts/rabbit-refresh-rebaseline.py`, which re-baselines ONLY the `SKILL.md`
tier of the snapshot.

This test exercises the REAL companion script as a subprocess and the REAL
deployed dispatchers, asserting:
  - after a SKILL.md change the reload advisory fires;
  - running rabbit-refresh-rebaseline.py clears it on the next Stop /
    UserPromptSubmit tick;
  - a concurrent HARD-restart change (a hook) is NOT cleared by the re-baseline;
  - a NEW SKILL.md change AFTER the re-baseline still fires a fresh advisory (the
    clear is not a permanent suppression).
Also asserts the dead `/reload-skills` prompt-match branch is gone from the
dispatcher source.
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
REBASELINE_SRC = RABBIT_CAGE / "scripts/rabbit-refresh-rebaseline.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"

RESTART_FRAGMENT = "restart ADVISED"
RELOAD_FRAGMENT = "reload ADVISED"
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

    # Deploy the companion script under its feature path so its
    # `parent.parent / hooks` import of restart_snapshot resolves.
    cage_dir = install_root / ".claude/features/rabbit-cage"
    (cage_dir / "scripts").mkdir(parents=True)
    (cage_dir / "hooks").mkdir(parents=True)
    shutil.copy2(REBASELINE_SRC, cage_dir / "scripts/rabbit-refresh-rebaseline.py")
    shutil.copy2(SNAPSHOT_SRC, cage_dir / "hooks/restart_snapshot.py")

    (install_root / ".claude/features").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REPO / ".claude/features/contract",
        install_root / ".claude/features/contract",
    )
    shutil.copytree(
        REPO / ".claude/features/rabbit-meta",
        install_root / ".claude/features/rabbit-meta",
    )
    shutil.copy2(RABBIT_CAGE_FEATURE_JSON, cage_dir / "feature.json")
    pol = install_root / ".claude/features/policy"
    pol.mkdir(parents=True)
    (pol / "philosophy.md").write_text("# stub\n")
    (pol / "spec-rules.md").write_text("# stub\n")
    (pol / "coding-rules.md").write_text("# stub\n")

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


def _run(target: Path, install_root: Path, stdin: str = ""):
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(target)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(install_root),
    )


def _stop(r):
    return _run(r / ".claude/hooks/stop-dispatcher.py", r)


def _session(r):
    return _run(r / ".claude/hooks/session-start-dispatcher.py", r)


def _ups(r, stdin=""):
    return _run(r / ".claude/hooks/user-prompt-submit-dispatcher.py", r, stdin)


def _refresh_rebaseline(r):
    return _run(
        r / ".claude/features/rabbit-cage/scripts/rabbit-refresh-rebaseline.py",
        r,
    )


def _sysmsg(proc) -> str:
    out = proc.stdout.strip()
    if not out:
        return ""
    try:
        return json.loads(out).get("systemMessage", "")
    except (json.JSONDecodeError, ValueError):
        return ""


def _has_reload(msg):
    return RELOAD_FRAGMENT in msg


def _has_restart(msg):
    return RESTART_FRAGMENT in msg


def _snapshot_session(r):
    proc = _session(r)
    assert proc.returncode == 0, f"session failed: {proc.stderr!r}"
    assert (r / SNAPSHOT_FILE).exists(), "SessionStart must write snapshot"


# --- t1: SKILL.md change → reload advisory fires; /rabbit-refresh clears it. --
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")

    pre = _ups(r)
    if not _has_reload(_sysmsg(pre)):
        bad(f"pre-refresh: expected reload advisory; sysmsg={_sysmsg(pre)!r}")
    else:
        ok("pre-refresh: reload advisory fires on a SKILL.md change")

    rb = _refresh_rebaseline(r)
    if rb.returncode != 0:
        bad(f"rebaseline script non-zero rc={rb.returncode} "
            f"stderr={rb.stderr.strip()!r}")
    else:
        ok("rabbit-refresh-rebaseline.py exits 0")

    for name, proc in (("Stop", _stop(r)), ("UserPromptSubmit", _ups(r))):
        msg = _sysmsg(proc)
        if proc.returncode != 0:
            bad(f"post-refresh {name} non-zero rc={proc.returncode}")
        elif _has_reload(msg):
            bad(f"post-refresh {name} reload advisory persists; sysmsg={msg!r}")
        else:
            ok(f"post-refresh {name} reload advisory cleared")


# --- t2: /rabbit-refresh does NOT clear a concurrent HARD-restart change. -----
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")
    (r / ".claude/hooks/some-hook.py").write_text("# CHANGED hook\n")

    rb = _refresh_rebaseline(r)
    if rb.returncode != 0:
        bad(f"mixed rebaseline non-zero rc={rb.returncode}")
    nxt = _stop(r)
    msg = _sysmsg(nxt)
    if not _has_restart(msg):
        bad(f"post-refresh hard-restart advisory wrongly cleared; "
            f"sysmsg={msg!r}")
    else:
        ok("post-refresh concurrent hook change still fires restart advisory")


# --- t3: a NEW SKILL.md change AFTER the re-baseline fires a fresh advisory. --
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")
    _refresh_rebaseline(r)
    # The first advisory is cleared; now a SECOND, genuinely new SKILL.md change.
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED AGAIN skill v3\n")
    proc = _ups(r)
    if not _has_reload(_sysmsg(proc)):
        bad(f"a NEW SKILL.md change after refresh must re-advise; "
            f"sysmsg={_sysmsg(proc)!r}")
    else:
        ok("a new SKILL.md change after refresh fires a fresh reload advisory")


# --- t4: the dead /reload-skills prompt-match branch is gone from dispatcher. -
ups_text = UPS_SRC.read_text()
if "/reload-skills" in ups_text and "== _RELOAD_SKILLS_COMMAND" in ups_text:
    bad("dispatcher still carries the dead /reload-skills prompt-match branch")
else:
    ok("dispatcher no longer prompt-matches the client-local /reload-skills")


print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
