#!/usr/bin/env python3
"""test-prune-worktrees.py — spec Inv 49 (added v0.43.0 for issue #628).

End-to-end tests for `scripts/prune-worktrees.py`, the tick-start orphan
sweep that bounds disk usage from parallel TDD dispatch. The sweep:

  - force-removes every leftover `agent-*` git worktree UNDER
    `<repo_root>/.claude/worktrees/` (then `git worktree prune`),
  - NEVER removes the main checkout, a non-`agent-*` worktree, or a path
    outside `.claude/worktrees/`,
  - is a clean no-op when there are no orphans,
  - bounds `<repo_root>/.rabbit/prompts/` by invoking the contract-owned
    `cleanup_old_prompts` API.

Every test builds a REAL temp git repo with REAL worktrees (git 2.48) so the
sweep exercises actual `git worktree` plumbing — it never touches the live
workspace. The script honors RABBIT_AUTO_EVOLVE_REPO_ROOT for isolation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SCRIPT = FEATURE_DIR / "scripts" / "prune-worktrees.py"

pass_n = 0
fail_n = 0


def ok(t: str, msg: str) -> None:
    global pass_n
    print(f"  PASS {t}: {msg}")
    pass_n += 1


def fail_t(t: str, msg: str) -> None:
    global fail_n
    print(f"  FAIL {t}: {msg}")
    fail_n += 1


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True,
    )


def _init_repo(repo: Path) -> None:
    """Create a real git repo with one commit so worktrees can be added."""
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")


def _add_worktree(repo: Path, rel_path: str, branch: str) -> Path:
    """Add a real worktree at <repo>/<rel_path> on a fresh branch."""
    wt = repo / rel_path
    wt.parent.mkdir(parents=True, exist_ok=True)
    r = _git(repo, "worktree", "add", "-q", "-b", branch, str(wt))
    if r.returncode != 0:
        raise RuntimeError(f"worktree add failed: {r.stderr}")
    return wt


def _run(repo: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RABBIT_AUTO_EVOLVE_REPO_ROOT"] = str(repo)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env, capture_output=True, text=True, cwd=str(repo),
    )


def _wt_paths(repo: Path) -> set[str]:
    """Set of worktree paths git currently tracks (resolved)."""
    r = _git(repo, "worktree", "list", "--porcelain")
    out = set()
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            out.add(str(Path(line[len("worktree "):]).resolve()))
    return out


print("test-prune-worktrees.py")

# --- t0: script exists ---
if SCRIPT.is_file():
    ok("exists", str(SCRIPT))
else:
    fail_t("exists", f"script not found: {SCRIPT}")

# --- t1: a leftover agent-* worktree under .claude/worktrees/ is pruned ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    _init_repo(repo)
    agent = _add_worktree(repo, ".claude/worktrees/agent-deadbeef01", "wt-a1")
    # dirty it so it mirrors a real changed TDD worktree the Agent tool kept.
    (agent / "scratch.txt").write_text("changed\n")
    r = _run(repo)
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("prune/agent", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif obj is None:
        fail_t("prune/agent", f"stdout not JSON: {r.stdout!r}")
    elif agent.exists():
        fail_t("prune/agent", "agent worktree dir still present after sweep")
    elif str(agent.resolve()) in _wt_paths(repo):
        fail_t("prune/agent", "git still tracks the agent worktree after prune")
    elif str(agent.resolve()) not in {str(Path(p).resolve()) for p in obj.get("removed", [])}:
        fail_t("prune/agent", f"removed list missing agent path: {obj.get('removed')!r}")
    else:
        ok("prune/agent", "leftover agent-* worktree force-removed and pruned")

# --- t2: the MAIN checkout is NEVER removed ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    _init_repo(repo)
    _add_worktree(repo, ".claude/worktrees/agent-cafe02", "wt-a2")
    r = _run(repo)
    if r.returncode != 0:
        fail_t("safety/main", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif not (repo / "README").is_file():
        fail_t("safety/main", "main checkout content was removed")
    elif str(repo) not in _wt_paths(repo):
        fail_t("safety/main", "git no longer tracks the main worktree")
    else:
        ok("safety/main", "main checkout untouched")

# --- t3: a NON-agent worktree is NEVER removed ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    _init_repo(repo)
    agent = _add_worktree(repo, ".claude/worktrees/agent-feed03", "wt-a3")
    # a sibling worktree whose basename does NOT match agent-*
    keep = _add_worktree(repo, ".claude/worktrees/release-staging", "wt-k3")
    r = _run(repo)
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    if r.returncode != 0:
        fail_t("safety/non-agent", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif not keep.exists():
        fail_t("safety/non-agent", "non-agent worktree was removed")
    elif str(keep.resolve()) not in _wt_paths(repo):
        fail_t("safety/non-agent", "git stopped tracking the non-agent worktree")
    elif agent.exists():
        fail_t("safety/non-agent", "agent worktree NOT removed (sweep no-op)")
    elif obj is not None and str(keep.resolve()) in {
            str(Path(p).resolve()) for p in obj.get("removed", [])}:
        fail_t("safety/non-agent", "non-agent path appeared in removed list")
    else:
        ok("safety/non-agent",
           "non-agent worktree kept; only agent-* removed")

# --- t4: an agent-* worktree OUTSIDE .claude/worktrees/ is NEVER removed ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    _init_repo(repo)
    # basename matches agent-* but it is NOT under .claude/worktrees/
    outside = _add_worktree(repo, "tmp/agent-outside04", "wt-o4")
    r = _run(repo)
    if r.returncode != 0:
        fail_t("safety/outside", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif not outside.exists():
        fail_t("safety/outside",
               "agent-* worktree OUTSIDE .claude/worktrees/ was removed")
    elif str(outside.resolve()) not in _wt_paths(repo):
        fail_t("safety/outside", "git stopped tracking the outside worktree")
    else:
        ok("safety/outside",
           "agent-* outside .claude/worktrees/ left untouched")

# --- t5: clean no-op when there are no orphans ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    _init_repo(repo)
    before = _wt_paths(repo)
    r = _run(repo)
    try:
        obj = json.loads(r.stdout)
    except json.JSONDecodeError:
        obj = None
    after = _wt_paths(repo)
    if r.returncode != 0:
        fail_t("noop", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif before != after:
        fail_t("noop", f"worktree set changed: {before} -> {after}")
    elif obj is None:
        fail_t("noop", f"stdout not JSON: {r.stdout!r}")
    elif obj.get("removed"):
        fail_t("noop", f"removed list non-empty on no-op: {obj.get('removed')!r}")
    else:
        ok("noop", "no orphans -> clean no-op, empty removed list")

# --- t6: prompt-dir bounding caps .rabbit/prompts/ ---
# Old prompt (>7d) must be deleted; fresh prompt must survive. Filenames match
# build-prompt.py's <id>-<pid>-<YYYYMMDD>-<HHMMSS>-<ms>.txt pattern.
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    _init_repo(repo)
    prompts = repo / ".rabbit" / "prompts"
    prompts.mkdir(parents=True)
    old_day = time.strftime("%Y%m%d", time.localtime(time.time() - 30 * 86400))
    new_day = time.strftime("%Y%m%d", time.localtime())
    old_f = prompts / f"feat-12345-{old_day}-101112-001.txt"
    new_f = prompts / f"feat-12345-{new_day}-101112-002.txt"
    old_f.write_text("old prompt\n")
    new_f.write_text("new prompt\n")
    r = _run(repo)
    if r.returncode != 0:
        fail_t("prompt-bound", f"exit {r.returncode}; stderr={r.stderr!r}")
    elif old_f.exists():
        fail_t("prompt-bound", "old (>7d) prompt was NOT pruned")
    elif not new_f.exists():
        fail_t("prompt-bound", "fresh prompt was wrongly pruned")
    else:
        ok("prompt-bound", "old prompt pruned, fresh prompt kept (cap honored)")

# --- t7: sweep succeeds (does not fail the tick) when prompts dir absent ---
with tempfile.TemporaryDirectory() as d:
    repo = Path(d).resolve()
    _init_repo(repo)
    r = _run(repo)
    if r.returncode != 0:
        fail_t("prompt-absent", f"exit {r.returncode}; stderr={r.stderr!r}")
    else:
        ok("prompt-absent", "missing .rabbit/prompts/ is a clean no-op")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
