#!/usr/bin/env python3
"""sync-tree.py — deterministic tick-start working-tree self-sync (Inv 38).

Usage:
  sync-tree.py        # emit {"status": ...} on stdout; exit 0 only on success

Per rabbit-auto-evolve spec.md Inv 38 (issue #524), the loop runs its phase
scripts from its LOCAL working-tree checkout. After it merges PRs to
`origin/dev` (via `gh pr merge`), local `dev` falls behind and subsequent
ticks run STALE script versions until a human manually fast-forwards. This
script self-syncs at TICK START so the whole tick executes one consistent
script version.

It performs the deterministic sync:

  1. Verify the working tree is clean of uncommitted TRACKED changes (the
     same condition as safety-check.py Inv 5 — `git diff --quiet` AND
     `git diff --cached --quiet`; untracked files are ignored). A dirty tree
     exits non-zero, failing loudly (do NOT sync over local edits).
  2. Run `git pull --ff-only origin dev`. On a non-fast-forwardable
     divergence `--ff-only` fails loudly (exit non-zero); the loop surfaces
     it and does NOT fall back to a non-ff merge.
  3. On success, emit a result line and best-effort log the sync outcome via
     tick-log.py.

`git pull`, NEVER `git merge` (the binding constraint). `settings.json`
declares `deny: ["Bash(git merge *)"]` — a permissions `deny`, which is
absolute (it beats any `allow` and even `defaultMode: bypassPermissions`).
So `git merge --ff-only origin/dev` is permission-denied. `git pull` is NOT
denied and fast-forwards cleanly. This script therefore uses
`git pull --ff-only origin dev` exclusively and NEVER calls `git merge`.

Resolution:
  - repo root via RABBIT_AUTO_EVOLVE_REPO_ROOT, else os.getcwd().
  - git binary via RABBIT_GIT_CMD (test seam, like RABBIT_CRONTAB_CMD),
    else the literal `git`.
  - state dir for tick-log via RABBIT_AUTO_EVOLVE_STATE_DIR (honored by
    tick-log.py), else <cwd>/.rabbit.

Status values emitted on stdout: "synced" (fast-forward applied or already
up to date), "dirty" (uncommitted tracked changes — no pull ran),
"diverged" (non-ff or other pull failure). Exit 0 only on "synced".

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys

# Import the sibling minimal logger in-process (matching how running-guard.py
# and schedule-decision.py reuse it) rather than re-deriving the log path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import importlib
    tick_log = importlib.import_module("tick-log")
except Exception:  # pragma: no cover - logging is best-effort
    tick_log = None


def _git_cmd():
    return os.environ.get("RABBIT_GIT_CMD", "git")


def _repo_root():
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT", os.getcwd())


def _git(repo_root, *args):
    """Run `git` in repo_root; return its CompletedProcess (text mode)."""
    return subprocess.run(
        [_git_cmd(), *args],
        cwd=repo_root, capture_output=True, text=True,
    )


def _log(decision, detail=""):
    """Best-effort append to the minimal tick log (never fatal)."""
    if tick_log is None:
        return
    try:
        tick_log.append(decision, detail)
    except Exception:  # pragma: no cover - logging is best-effort
        pass


def _emit(status, detail=""):
    obj = {"status": status}
    if detail:
        obj["detail"] = detail
    json.dump(obj, sys.stdout)
    sys.stdout.write("\n")


def sync():
    repo_root = _repo_root()

    # --- Step A: cleanliness (safety-check.py Inv 5 condition) -----------
    # Untracked files are ignored; only tracked M/A/D/R block the sync.
    unstaged = _git(repo_root, "diff", "--quiet").returncode
    staged = _git(repo_root, "diff", "--cached", "--quiet").returncode
    if unstaged != 0 or staged != 0:
        which = "unstaged" if unstaged != 0 else "staged"
        detail = f"tracked file has {which} modifications — refusing to sync"
        sys.stderr.write(f"sync-tree: {detail}\n")
        _emit("dirty", detail)
        _log("sync: dirty tree", detail)
        return 1

    # --- Step B: git pull --ff-only origin dev (NEVER git merge) ---------
    pull = _git(repo_root, "pull", "--ff-only", "origin", "dev")
    if pull.returncode != 0:
        detail = (pull.stderr or pull.stdout or "non-fast-forward").strip()
        sys.stderr.write(f"sync-tree: pull failed: {detail}\n")
        _emit("diverged", detail)
        _log("sync: diverged", detail)
        return 1

    # --- Step C: success ------------------------------------------------
    _emit("synced")
    _log("sync: tree synced", "git pull --ff-only origin dev")
    return 0


def main():
    argparse.ArgumentParser(
        description="Tick-start working-tree self-sync: verify the tree is "
                    "clean of tracked changes, then `git pull --ff-only "
                    "origin dev` (NEVER git merge — it is permission-denied). "
                    "Fails loudly on a dirty or divergent tree (Inv 38 / "
                    "#524). Honors RABBIT_AUTO_EVOLVE_REPO_ROOT and "
                    "RABBIT_GIT_CMD."
    ).parse_args()
    return sync()


if __name__ == "__main__":
    sys.exit(main())
