#!/usr/bin/env python3
"""test-reload-skills-clears-reload-advisory.py — e2e: issue #1173 (Inv 54f).

The tiered `/reload-skills` advisory (Inv 54e, issue #1156) must CLEAR after the
user actually runs `/reload-skills`. Before this fix the snapshot baseline was
re-written only on SessionStart, so the reload-tier advisory persisted forever:
`/reload-skills` is a Claude Code built-in that does NOT start a session, so it
never updated rabbit-cage's snapshot, and the "no restart needed" nag fired on
every Stop / UserPromptSubmit indefinitely.

The fix: when the UserPromptSubmit dispatcher observes the submitted prompt is
`/reload-skills`, it re-baselines ONLY the `SKILL.md`-tier keys of the snapshot
(so the reload-tier advisory clears) while leaving the hard-restart-tier keys
(hooks / settings / CLAUDE.md / agents) UNTOUCHED — a genuine hook/settings/
CLAUDE.md/agent change still legitimately requires a restart.

This is an end-to-end test: it builds a fake install root with the deployed
dispatchers + shared lib, runs SessionStart to snapshot, mutates surfaces on
disk, runs the UserPromptSubmit dispatcher as a subprocess WITH a stdin prompt
payload, and asserts on the emitted JSON.
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


def _run(dispatcher: Path, install_root: Path, stdin: str = ""):
    env = {**os.environ, "RABBIT_ROOT": str(install_root)}
    return subprocess.run(
        [sys.executable, str(dispatcher)],
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


def _sysmsg(proc) -> str:
    out = proc.stdout.strip()
    if not out:
        return ""
    try:
        return json.loads(out).get("systemMessage", "")
    except (json.JSONDecodeError, ValueError):
        return ""


def _has_reload(msg):
    return RELOAD_FRAGMENT in msg and RELOAD_COMMAND in msg


def _has_restart(msg):
    return RESTART_FRAGMENT in msg


def _snapshot_session(r):
    proc = _session(r)
    assert proc.returncode == 0, f"session failed: {proc.stderr!r}"
    assert (r / SNAPSHOT_FILE).exists(), "SessionStart must write snapshot"


# --- t1: a SKILL.md change + /reload-skills prompt → reload advisory CLEARS. -
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")

    # Sanity: before the reload prompt, the reload advisory fires.
    pre = _ups(r)
    if not _has_reload(_sysmsg(pre)):
        bad(f"pre-reload: expected reload advisory; sysmsg={_sysmsg(pre)!r}")
    else:
        ok("pre-reload: reload advisory fires on a SKILL.md change")

    # Submit a /reload-skills prompt — the dispatcher should re-baseline the
    # SKILL.md tier so the advisory clears on THIS emission.
    reload_stdin = json.dumps(
        {"hook_event_name": "UserPromptSubmit", "prompt": "/reload-skills"})
    post = _ups(r, reload_stdin)
    if post.returncode != 0:
        bad(f"reload UPS non-zero rc={post.returncode} "
            f"stderr={post.stderr.strip()!r}")
    elif _has_reload(_sysmsg(post)):
        bad(f"reload prompt did NOT clear reload advisory; "
            f"sysmsg={_sysmsg(post)!r}")
    else:
        ok("reload prompt clears the reload advisory on its own emission")

    # After the reload, subsequent ticks (Stop + plain UserPromptSubmit) must
    # STAY silent — the snapshot's SKILL.md key was re-baselined on disk.
    for name, proc in (("Stop", _stop(r)), ("UserPromptSubmit", _ups(r))):
        msg = _sysmsg(proc)
        if proc.returncode != 0:
            bad(f"post-reload {name} non-zero rc={proc.returncode}")
        elif _has_reload(msg):
            bad(f"post-reload {name} reload advisory persists; sysmsg={msg!r}")
        else:
            ok(f"post-reload {name} reload advisory stays cleared")


# --- t2: reload does NOT clear a concurrent HARD-restart change. -------------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    # BOTH a SKILL.md and a hook change happen since the session snapshot.
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")
    (r / ".claude/hooks/some-hook.py").write_text("# CHANGED hook\n")

    reload_stdin = json.dumps(
        {"hook_event_name": "UserPromptSubmit", "prompt": "/reload-skills"})
    post = _ups(r, reload_stdin)
    msg = _sysmsg(post)
    if post.returncode != 0:
        bad(f"mixed reload UPS non-zero rc={post.returncode} "
            f"stderr={post.stderr.strip()!r}")
    elif not _has_restart(msg):
        bad(f"reload wrongly cleared the hard-restart advisory; "
            f"sysmsg={msg!r}")
    else:
        ok("reload leaves the concurrent hook change's restart advisory intact")

    # And the hard-restart advisory must persist on the NEXT tick too (the
    # hook tier was never re-baselined).
    nxt = _stop(r)
    if not _has_restart(_sysmsg(nxt)):
        bad(f"post-reload hook restart advisory lost on next tick; "
            f"sysmsg={_sysmsg(nxt)!r}")
    else:
        ok("post-reload hook restart advisory persists on the next tick")


# --- t3: a non-/reload-skills prompt does NOT clear the reload advisory. -----
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")

    other_stdin = json.dumps(
        {"hook_event_name": "UserPromptSubmit", "prompt": "do something else"})
    post = _ups(r, other_stdin)
    if not _has_reload(_sysmsg(post)):
        bad(f"unrelated prompt wrongly cleared reload advisory; "
            f"sysmsg={_sysmsg(post)!r}")
    else:
        ok("an unrelated prompt leaves the reload advisory firing")


print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
