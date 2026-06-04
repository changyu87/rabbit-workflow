#!/usr/bin/env python3
"""prune-worktrees.py — tick-start orphan sweep (Inv 53, issue #628).

Parallel TDD dispatch (worktree isolation, #430) creates one git worktree per
subagent under `.claude/worktrees/agent-*`. The Agent tool auto-removes a
dispatch worktree ONLY when it is unchanged on exit; a TDD worktree is always
changed, so it is NEVER auto-removed and the `agent-*` worktrees accumulate
(~9-14 MB each — 61 leftover / 577 MB observed). `.rabbit/prompts/` likewise
grew unbounded (264 files / 23 MB observed). This script bounds BOTH.

SAFETY BY SEQUENCING. This sweep is invoked from `run-tick-phases.py`'s
pre-dispatch segment, BEFORE Phase 5 dispatch begins. At tick start no dispatch
is live, so every existing `agent-*` worktree is an orphan from a prior or
interrupted tick and is safe to force-remove. The sweep:

  - force-removes (`git worktree remove --force`) every worktree
    `git worktree list --porcelain` reports whose basename matches `agent-*`
    AND that lies under `<repo_root>/.claude/worktrees/`, then runs a single
    `git worktree prune`;
  - NEVER removes the main checkout, a non-`agent-*` path, or a path outside
    `.claude/worktrees/`;
  - is a clean no-op when there are no orphans;
  - never fails the tick on a sweep error — a failed remove on one path is
    recorded and the sweep continues (disk hygiene must never block evolution).

It then bounds `<repo_root>/.rabbit/prompts/` by INVOKING the contract-owned
`contract.lib.runtime.cleanup_old_prompts(max_age_days=7, repo_root=...)` API
(a cross-scope INVOKE declared in this feature's `docs/contract.md`
`invokes.modules`; rabbit-auto-evolve does NOT edit the contract feature).

A single JSON summary is emitted on stdout:
  {"removed": [...], "kept": [...], "prompts_bounded": <bool>, "status": "ok"}

`<repo_root>` defaults to `os.getcwd()`; overridable via the
`RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

Version: 1.0.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill, or the Agent tool learns to
auto-remove changed dispatch worktrees on exit.
"""

import fnmatch
import json
import os
import subprocess
import sys

PROMPT_MAX_AGE_DAYS = 7


def _repo_root():
    return os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT", os.getcwd())


def _list_worktrees(repo_root):
    """Return the list of worktree paths git tracks, via porcelain output.
    Empty list on any git failure (sweep degrades to a no-op, never aborts)."""
    proc = subprocess.run(
        ["git", "-C", repo_root, "worktree", "list", "--porcelain"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return []
    paths = []
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(line[len("worktree "):])
    return paths


def _is_orphan_agent_worktree(path, repo_root):
    """True only for a path whose basename matches `agent-*` AND that lies
    directly under `<repo_root>/.claude/worktrees/`. The main checkout and any
    non-`agent-*` or out-of-tree path is excluded."""
    worktrees_dir = os.path.realpath(
        os.path.join(repo_root, ".claude", "worktrees"))
    real = os.path.realpath(path)
    parent = os.path.dirname(real)
    if parent != worktrees_dir:
        return False
    return fnmatch.fnmatch(os.path.basename(real), "agent-*")


def _remove_worktree(repo_root, path):
    """git worktree remove --force <path>. Returns True on success."""
    proc = subprocess.run(
        ["git", "-C", repo_root, "worktree", "remove", "--force", path],
        capture_output=True, text=True,
    )
    return proc.returncode == 0


def _prune(repo_root):
    subprocess.run(
        ["git", "-C", repo_root, "worktree", "prune"],
        capture_output=True, text=True,
    )


def _bound_prompts(repo_root):
    """Invoke the contract-owned cleanup_old_prompts to bound .rabbit/prompts/.
    Lazy-import contract.lib.runtime by inserting the contract feature dir onto
    sys.path (mirrors set-evolve-mode.py's _import_mutation pattern). Returns
    True when the cleanup ran without raising; failures are swallowed so disk
    hygiene never blocks the tick."""
    here = os.path.dirname(os.path.abspath(__file__))
    # scripts/ -> rabbit-auto-evolve/ -> features/ -> contract/
    contract_dir = os.path.normpath(os.path.join(here, "..", "..", "contract"))
    if contract_dir not in sys.path:
        sys.path.insert(0, contract_dir)
    try:
        from lib import runtime  # noqa: PLC0415
        runtime.cleanup_old_prompts(
            max_age_days=PROMPT_MAX_AGE_DAYS, repo_root=repo_root)
        return True
    except Exception:  # noqa: BLE001 — never block the tick on a cleanup error
        return False


def sweep(repo_root):
    """Run the orphan sweep + prompt bounding. Returns the summary dict."""
    removed = []
    kept = []
    for path in _list_worktrees(repo_root):
        if _is_orphan_agent_worktree(path, repo_root):
            if _remove_worktree(repo_root, path):
                removed.append(path)
            else:
                # A stuck worktree is recorded but never aborts the sweep.
                kept.append(path)
        else:
            kept.append(path)
    if removed:
        _prune(repo_root)
    prompts_bounded = _bound_prompts(repo_root)
    return {
        "removed": removed,
        "kept": kept,
        "prompts_bounded": prompts_bounded,
        "status": "ok",
    }


def main():
    result = sweep(_repo_root())
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
