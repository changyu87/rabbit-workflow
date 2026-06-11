#!/usr/bin/env python3
"""test-restart-advisory-on-disk-change.py — e2e: issue #1117.

rabbit's counter-drift promise (loaded skills/subagents/hooks monitored for a
newer on-disk version, restart recommended on change) must be honored for EVERY
restart-sensitive surface and EVERY update path — not just the
`/rabbit-update install` path that writes the `.rabbit-update-restart-needed`
marker.

The mechanism under test (rabbit-cage-owned, in scope):
  - SessionStart snapshots a content-hash signature of the loaded
    restart-sensitive surfaces into `<repo_root>/.rabbit-restart-snapshot`
    (the baseline = what the running session has loaded).
  - The Stop and UserPromptSubmit dispatchers recompute that signature and,
    when it differs from the snapshot, surface ONE `restart ADVISED` line.
  - The advisory fires WITHOUT `/rabbit-update install` having run (it covers
    the git-pull / direct-edit / IDE-sync update paths), because the signal is
    a pure on-disk re-hash, not a marker only `install` writes.

The restart-sensitive surface set MUST cover, individually:
  - a `.claude/hooks/` file
  - a `.claude/settings*.json` file
  - root `CLAUDE.md`
  - a `.claude/skills/*/SKILL.md` file  (the #1117 gap)
  - a `.claude/agents/*.md` file         (the #1117 gap)

A change to a NON-restart-sensitive file (e.g. a docs file) MUST NOT trigger
the advisory (no false positive).

This is an end-to-end test: it builds a fake install root with the deployed
dispatchers + shared lib, runs SessionStart to snapshot, mutates ONE surface on
disk (simulating a non-`install` update path), runs the Stop and
UserPromptSubmit dispatchers as subprocesses, and asserts on the emitted JSON.
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
STOP_SRC = RABBIT_CAGE / "hooks/stop-dispatcher.py"
SESSION_SRC = RABBIT_CAGE / "hooks/session-start-dispatcher.py"
UPS_SRC = RABBIT_CAGE / "hooks/user-prompt-submit-dispatcher.py"
DISPATCHER_LIB_SRC = RABBIT_CAGE / "hooks/_dispatcher_lib.py"
SNAPSHOT_SRC = RABBIT_CAGE / "hooks/restart_snapshot.py"
RABBIT_CAGE_FEATURE_JSON = RABBIT_CAGE / "feature.json"

# The advisory must read as OPTIONAL (distinct from any hard pause banner).
ADVISORY_FRAGMENT = "restart ADVISED"
# Inv 54(c): the advisory line ends with a wall-clock timestamp so the reader
# can judge freshness — `(as of HH:MM:SS ZZZ)`, the `%H:%M:%S %Z` format the
# universal Stop turn-end timestamp (Inv 57) uses. `%Z` may render empty in a
# bare tz so the zone label group is optional.
TIMESTAMP_RE = re.compile(r"\(as of \d{2}:\d{2}:\d{2}(?: \S+)?\)")
# Inv 54(c) (#1124): the advisory line renders in YELLOW so it signals
# advisory/warning severity (distinct from a hard red error) and is not missed.
# rabbit_print's yellow ANSI open code is ESC[33m; the line ends with the reset
# ESC[0m. The yellow open MUST precede the advisory phrase on the rendered line.
YELLOW_OPEN = "\x1b[33m"
ANSI_RESET = "\x1b[0m"
# A yellow-wrapped segment that contains the advisory phrase before its reset.
YELLOW_ADVISORY_RE = re.compile(
    r"\x1b\[33m[^\x1b]*restart ADVISED \(not required\)[^\x1b]*\x1b\[0m")
# The auto-evolve advisory marker must NOT be required for this path.
AE_ADVISORY_MARKER = ".rabbit-auto-evolve-restart-advised"
# The /rabbit-update install marker — must NOT be required for this path.
UPDATE_MARKER = ".rabbit-update-restart-needed"
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
    agents_dir = install_root / ".claude/agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "tdd-subagent.md").write_text("# original agent v1\n")
    # A NON-restart-sensitive file (control).
    (install_root / "docs").mkdir()
    (install_root / "docs/notes.md").write_text("original docs\n")

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


# Each HARD-restart surface: (label, relative path, new content). Under the
# Inv 54(e) tiering, a `.claude/skills/*/SKILL.md`-only change is NOT a
# hard-restart surface — it yields the cheaper `/reload-skills` advisory, so it
# is excluded here and exercised by its own reload-tier case (t1b) below and by
# test-restart-advisory-tiered-by-change-type.py.
SURFACES = [
    ("hook", ".claude/hooks/some-hook.py", "# CHANGED hook\n"),
    ("settings", ".claude/settings.json", '{"changed": 2}\n'),
    ("CLAUDE.md", "CLAUDE.md", "# CHANGED claude md\n"),
    ("agent", ".claude/agents/tdd-subagent.md", "# CHANGED agent v2\n"),
]
# The reload-tier fragment for the SKILL.md-only path (Inv 54(e)).
RELOAD_FRAGMENT = "reload ADVISED"


def _snapshot_session(r):
    """SessionStart must write the snapshot baseline."""
    proc = _session(r)
    assert proc.returncode == 0, f"session failed: {proc.stderr!r}"
    return proc


# --- t1..t4: each HARD-restart surface, changed individually, triggers
#     the full-restart advisory on BOTH Stop and UserPromptSubmit. -----------
for label, rel, new in SURFACES:
    with tempfile.TemporaryDirectory() as td:
        r = _build_install_root(Path(td).resolve())
        _snapshot_session(r)
        if not (r / SNAPSHOT_FILE).exists():
            bad(f"[{label}] SessionStart must write {SNAPSHOT_FILE}")
            continue
        # No install marker, no auto-evolve advisory marker — prove the
        # advisory fires WITHOUT /rabbit-update install.
        assert not (r / UPDATE_MARKER).exists()
        assert not (r / AE_ADVISORY_MARKER).exists()
        # Simulate a non-install update path: a direct on-disk edit.
        target = r / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new)

        stop = _stop(r)
        if stop.returncode == 0 and ADVISORY_FRAGMENT in _sysmsg(stop):
            ok(f"[{label}] Stop surfaces restart advisory after on-disk change")
        else:
            bad(f"[{label}] Stop missing advisory: rc={stop.returncode} "
                f"sysmsg={_sysmsg(stop)!r} stderr={stop.stderr.strip()!r}")

        ups = _ups(r)
        if ups.returncode == 0 and ADVISORY_FRAGMENT in _sysmsg(ups):
            ok(f"[{label}] UserPromptSubmit surfaces restart advisory")
        else:
            bad(f"[{label}] UserPromptSubmit missing advisory: "
                f"rc={ups.returncode} sysmsg={_sysmsg(ups)!r} "
                f"stderr={ups.stderr.strip()!r}")


# --- t1b: a SKILL.md-only change → the cheaper /reload-skills advisory (Inv
#     54(e)), NOT the full-restart line, on BOTH Stop and UserPromptSubmit. ---
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / ".claude/skills/rabbit-feature-touch/SKILL.md").write_text(
        "# CHANGED skill v2\n")
    stop = _stop(r)
    smsg = _sysmsg(stop)
    if stop.returncode == 0 and RELOAD_FRAGMENT in smsg \
            and ADVISORY_FRAGMENT not in smsg:
        ok("[skill] Stop surfaces /reload-skills advisory (not full restart)")
    else:
        bad(f"[skill] Stop wrong tier: sysmsg={smsg!r} "
            f"stderr={stop.stderr.strip()!r}")
    ups = _ups(r)
    umsg = _sysmsg(ups)
    if ups.returncode == 0 and RELOAD_FRAGMENT in umsg \
            and ADVISORY_FRAGMENT not in umsg:
        ok("[skill] UserPromptSubmit surfaces /reload-skills advisory")
    else:
        bad(f"[skill] UPS wrong tier: sysmsg={umsg!r} "
            f"stderr={ups.stderr.strip()!r}")


# --- t6: NO change at all → no advisory (no false positive). ---------------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    stop = _stop(r)
    if stop.returncode == 0 and ADVISORY_FRAGMENT not in _sysmsg(stop):
        ok("unchanged surfaces → Stop emits NO restart advisory")
    else:
        bad(f"unchanged → unexpected advisory: sysmsg={_sysmsg(stop)!r}")
    ups = _ups(r)
    if ups.returncode == 0 and ADVISORY_FRAGMENT not in _sysmsg(ups):
        ok("unchanged surfaces → UserPromptSubmit emits NO restart advisory")
    else:
        bad(f"unchanged → unexpected UPS advisory: sysmsg={_sysmsg(ups)!r}")


# --- t7: NON-restart-sensitive file changed → no advisory (no false +). ----
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / "docs/notes.md").write_text("CHANGED docs only\n")
    stop = _stop(r)
    if stop.returncode == 0 and ADVISORY_FRAGMENT not in _sysmsg(stop):
        ok("non-sensitive docs change → Stop emits NO advisory")
    else:
        bad(f"docs change wrongly triggered advisory: sysmsg={_sysmsg(stop)!r}")


# --- t8: SessionStart re-baselines (a restart clears the advisory). --------
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / "CLAUDE.md").write_text("# CHANGED again\n")
    stop = _stop(r)
    assert ADVISORY_FRAGMENT in _sysmsg(stop), "precondition: advisory present"
    # A new SessionStart = a restart: re-snapshot the now-current on-disk
    # state, so the advisory clears on the next Stop.
    _snapshot_session(r)
    stop2 = _stop(r)
    if stop2.returncode == 0 and ADVISORY_FRAGMENT not in _sysmsg(stop2):
        ok("SessionStart re-baselines → advisory clears after restart")
    else:
        bad(f"advisory did not clear after re-snapshot: "
            f"sysmsg={_sysmsg(stop2)!r}")


# --- t9: generated bytecode churn (__pycache__/*.pyc) → no false advisory. --
#     Importing the deployed hooks creates .pyc files mid-session; those are not
#     loaded artifacts and must be excluded from the signature.
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    # Wipe any __pycache__ created so far, then force a fresh dispatcher import
    # which regenerates .pyc AFTER the snapshot was taken.
    for pc in r.rglob("__pycache__"):
        shutil.rmtree(pc, ignore_errors=True)
    stop = _stop(r)  # re-imports the hooks → new .pyc under .claude/hooks
    # The .pyc churn must NOT be read as a restart-sensitive surface change.
    if stop.returncode == 0 and ADVISORY_FRAGMENT not in _sysmsg(stop):
        ok("bytecode (.pyc) churn → NO false restart advisory")
    else:
        bad(f"bytecode churn wrongly triggered advisory: sysmsg={_sysmsg(stop)!r}")


# --- t10: the surfaced advisory line carries a wall-clock timestamp (#1123). --
#     Inv 54(c): freshness must be judgeable — the line ends with
#     `(as of HH:MM:SS ZZZ)`, on BOTH the Stop and UserPromptSubmit paths.
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / "CLAUDE.md").write_text("# CHANGED for timestamp check\n")

    stop = _stop(r)
    stop_msg = _sysmsg(stop)
    if (stop.returncode == 0 and ADVISORY_FRAGMENT in stop_msg
            and TIMESTAMP_RE.search(stop_msg)):
        ok("Stop advisory line carries a wall-clock timestamp (as of HH:MM:SS)")
    else:
        bad(f"Stop advisory missing timestamp: sysmsg={stop_msg!r} "
            f"stderr={stop.stderr.strip()!r}")

    ups = _ups(r)
    ups_msg = _sysmsg(ups)
    if (ups.returncode == 0 and ADVISORY_FRAGMENT in ups_msg
            and TIMESTAMP_RE.search(ups_msg)):
        ok("UserPromptSubmit advisory line carries a wall-clock timestamp")
    else:
        bad(f"UserPromptSubmit advisory missing timestamp: sysmsg={ups_msg!r} "
            f"stderr={ups.stderr.strip()!r}")


# --- t11: the surfaced advisory line renders in YELLOW (#1124). --------------
#     Inv 54(c): the advisory `print` payload carries color yellow so the line
#     renders with the yellow ANSI marker (ESC[33m … ESC[0m) wrapping the
#     advisory phrase, on BOTH the Stop and UserPromptSubmit paths. The yellow
#     open must appear BEFORE the advisory phrase (not the green ESC[32m).
with tempfile.TemporaryDirectory() as td:
    r = _build_install_root(Path(td).resolve())
    _snapshot_session(r)
    (r / "CLAUDE.md").write_text("# CHANGED for yellow check\n")

    stop = _stop(r)
    stop_msg = _sysmsg(stop)
    if (stop.returncode == 0 and ADVISORY_FRAGMENT in stop_msg
            and YELLOW_ADVISORY_RE.search(stop_msg)):
        ok("Stop advisory line renders in yellow (ESC[33m wraps the phrase)")
    else:
        bad(f"Stop advisory not yellow: sysmsg={stop_msg!r} "
            f"stderr={stop.stderr.strip()!r}")

    ups = _ups(r)
    ups_msg = _sysmsg(ups)
    if (ups.returncode == 0 and ADVISORY_FRAGMENT in ups_msg
            and YELLOW_ADVISORY_RE.search(ups_msg)):
        ok("UserPromptSubmit advisory line renders in yellow (ESC[33m)")
    else:
        bad(f"UserPromptSubmit advisory not yellow: sysmsg={ups_msg!r} "
            f"stderr={ups.stderr.strip()!r}")


print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
