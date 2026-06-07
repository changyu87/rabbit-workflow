#!/usr/bin/env python3
"""clean-dispatch-leaks.py — deterministic, defense-in-depth pre-merge cleanup
of KNOWN worktree-dispatch leak-class noise from the dispatcher's MAIN working
tree (Inv 43 / issue #583; Inv 44 / issue #596).

Worktree-isolated Phase 5 dispatches sometimes leave working-tree noise in the
dispatcher's main tree because a subagent's process cwd is occasionally the
main/shared checkout (not its worktree) when it runs its LOCK / tdd-step
bookkeeping — a harness limitation the cwd-based `_repo_root` fix in #589
reduced but did not eliminate. Left in place, this noise trips safety-check
Inv 5 ("no uncommitted tracked-file modifications"), which makes merge-prs.py
SKIP every PR in the batch.

A more severe variant of the SAME root cause (#596): a subagent's
`git checkout -B <branch> origin/<target>` runs in the MAIN checkout and
switches the dispatcher's MAIN HEAD onto a feature branch. safety-check Inv 1
("branch is the integration target") then fails and merge-prs.py skips the
whole batch with a CLEAN tree (so this is NOT the #583 file-leak path).

`run-tick-phases.py run_post_dispatch` invokes this script as the FIRST action
of Phase 6, BEFORE merge-prs.py. The cleanup runs the branch-restore FIRST (so
the subsequent file cleanup and the merge see the right branch), then handles
ONLY the known file-leak classes and FAILS LOUDLY on anything else:

  0. **Leaked HEAD switch (#596).** The restore is INTEGRATION-TARGET-AWARE
     (Inv 61): the target is resolved via integration_target.resolve_target()
     (`dev` during the coexistence default, `main` post-cutover), NOT a
     hardcoded `dev`. If the main repo's HEAD is NOT the resolved target:
     - When the working tree is CLEAN and the branch has NO un-pushed unique
       commits (every local commit is on its `origin/<branch>` remote), restore
       with `git checkout <target>` — the feature work lives safely on its
       pushed branch.
     - When the tree is DIRTY or the branch has un-pushed unique commits,
       REFUSE loudly (non-zero) and do NOT switch/discard — let the tick abort
       (Inv 20) so a human/next-tick investigates. Mirrors the unexpected-dirt
       refusal below.
  1. Untracked stray `.rabbit-scope-active-*` markers at the repo root are
     removed.
  2. A TRACKED `<feature>/feature.json` whose diff vs HEAD touches ONLY the
     loop-bookkeeping keys (BOOKKEEPING_KEYS below) is restored to HEAD.
  3. ANY other tracked modification (a doc/spec/contract/CHANGELOG edit, a
     non-bookkeeping feature.json change, etc.) is NEVER silently discarded:
     the script reports it on stderr and exits NON-ZERO so the tick aborts
     (Inv 20) and a genuine uncommitted change is never destroyed. This is the
     critical safety property — clean ONLY known leak-class noise.

What was cleaned is logged via tick-log.py (Inv 36) so the cleanup is
observable. On a clean tree already on the resolved integration target the
script is a no-op (exit 0, nothing logged).

Resolution:
  - repo root via `RABBIT_AUTO_EVOLVE_REPO_ROOT`, else `git rev-parse
    --show-toplevel` from the cwd, else `os.getcwd()`.
  - state dir (for the tick log) via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else
    `<repo_root>/.rabbit` (matching tick-log.py's resolution when run with
    cwd == repo root).

Exit code: 0 on a successful cleanup or no-op; non-zero on unexpected dirt, a
leaked HEAD switch that cannot be safely restored (reported on stderr), or a
git failure. The script never discards an unexpected change or un-pushed work.

Version: 1.2.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys

# Resolve the loop's integration target (Inv 61) so the leaked-branch detection
# and restore key off the RESOLVED target (dev during the coexistence default,
# main post-cutover) — NOT a hardcoded `dev`. Mirrors sync-tree.py's reuse of
# the sibling module. The filename has an underscore, so a normal import works
# once the script's own dir is on sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integration_target

# The loop-bookkeeping keys a tdd-step / LOCK write touches in feature.json.
# A tracked feature.json modification is RESTORED only when its diff vs HEAD
# touches a subset of these keys — anything else is unexpected dirt.
BOOKKEEPING_KEYS = frozenset({
    "tdd_last_cycle_impl_commit",
    "tdd_state",
    "updated",
    "spec_no_change_reason",
    "_pre_touch_state",
})


def _repo_root():
    env = os.environ.get("RABBIT_AUTO_EVOLVE_REPO_ROOT")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return os.getcwd()


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args],
                          capture_output=True, text=True)


def _current_branch(repo):
    """The current branch name, or '' on a detached HEAD / failure."""
    out = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return out.stdout.strip() if out.returncode == 0 else ""


def _tree_dirty(repo):
    """True iff a tracked file has staged or unstaged modifications (the same
    Inv 5 view safety-check enforces). Untracked files do not count."""
    unstaged = _git(repo, "diff", "--quiet").returncode
    staged = _git(repo, "diff", "--cached", "--quiet").returncode
    return unstaged != 0 or staged != 0


def _has_unpushed_unique_commits(repo, branch):
    """True iff `branch` has local commits NOT present on its `origin/<branch>`
    remote (work that restoring to the integration target would orphan). A
    branch with no matching remote-tracking ref is treated as un-pushed
    (conservative)."""
    remote_ref = f"origin/{branch}"
    if _git(repo, "rev-parse", "--verify", "--quiet", remote_ref).returncode != 0:
        # No remote counterpart — assume there is unique local work to protect.
        return True
    out = _git(repo, "rev-list", "--count", f"{remote_ref}..{branch}")
    if out.returncode != 0:
        return True
    try:
        return int(out.stdout.strip()) > 0
    except ValueError:
        return True


def _log(decision, detail=""):
    """Append a tick-log line (Inv 36). Best-effort: import the sibling
    tick-log.py module so the log-path resolution stays in one place."""
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "tick_log", os.path.join(here, "tick-log.py"))
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.append(decision, detail)
    except Exception:
        pass


def _porcelain(repo):
    """Return git status --porcelain lines as (xy, path) tuples. Renames are
    reported with the destination path."""
    proc = _git(repo, "status", "--porcelain")
    entries = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        xy = line[:2]
        rest = line[3:]
        # Renames/copies show "old -> new"; take the new path.
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        entries.append((xy, rest))
    return entries


def _is_bookkeeping_only_feature_json(repo, path):
    """True iff `path` is a `<feature>/feature.json` whose tracked diff vs HEAD
    changes ONLY loop-bookkeeping keys (added, removed, or value-changed)."""
    if os.path.basename(path) != "feature.json":
        return False
    head = _git(repo, "show", f"HEAD:{path}")
    if head.returncode != 0:
        return False
    try:
        old = json.loads(head.stdout)
    except ValueError:
        return False
    try:
        with open(os.path.join(repo, path)) as f:
            new = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    changed = set()
    for k in set(old) | set(new):
        if old.get(k) != new.get(k):
            changed.add(k)
    if not changed:
        return False
    return changed <= BOOKKEEPING_KEYS


def clean(repo):
    """Perform the cleanup on `repo`'s working tree.

    Returns (exit_code, cleaned, refused):
      cleaned  — list of human-readable descriptions of what was cleaned.
      refused  — list of (path, reason) for unexpected tracked dirt.
    On any refusal the exit code is 1 and NOTHING in the refused set is
    touched (the restore phase runs only when no refusal occurred)."""
    cleaned = []
    refused = []
    restore_paths = []
    remove_markers = []

    # Step 0 (#596): detect + restore a leaked main-HEAD branch switch FIRST,
    # so the file cleanup below and the subsequent merge see the right branch.
    # The leak is "HEAD is not the RESOLVED integration target" (Inv 61: dev
    # during the coexistence default, main post-cutover) — NOT "HEAD != dev".
    # Hardcoding `dev` would wrongly treat a live `main` HEAD as a leak and
    # switch the dispatcher off `main`.
    target = integration_target.resolve_target()
    branch = _current_branch(repo)
    if branch and branch != target:
        if _tree_dirty(repo) or _has_unpushed_unique_commits(repo, branch):
            # Un-pushed work or uncommitted dirt on the leaked branch — REFUSE
            # loudly; never discard it by switching away.
            refused.append((
                branch,
                "leaked HEAD switch with dirty tree or un-pushed unique "
                "commits; refusing to switch (Inv 44)",
            ))
            return 1, cleaned, refused
        co = _git(repo, "checkout", target)
        if co.returncode != 0:
            refused.append((branch,
                            f"could not restore HEAD to {target}: {co.stderr.strip()}"))
            return 1, cleaned, refused
        cleaned.append(f"restored leaked HEAD switch from {branch} to {target}")

    for xy, path in _porcelain(repo):
        x, y = xy[0], xy[1]
        untracked = (xy == "??")
        if untracked:
            base = os.path.basename(path)
            if base.startswith(".rabbit-scope-active-") and "/" not in path.rstrip("/"):
                remove_markers.append(path)
            # Other untracked files cannot affect a merge (safety-check Inv 5
            # ignores them); leave them alone.
            continue
        # A tracked modification (M/A/D/R, staged or unstaged).
        if _is_bookkeeping_only_feature_json(repo, path):
            restore_paths.append(path)
        else:
            refused.append((path, f"unexpected tracked change ({xy.strip()})"))

    if refused:
        # Do NOT touch anything when unexpected dirt is present: refuse loudly
        # so the tick aborts (Inv 20) without destroying a genuine change.
        return 1, cleaned, refused

    for path in remove_markers:
        try:
            os.unlink(os.path.join(repo, path))
            cleaned.append(f"removed stray marker {path}")
        except OSError as e:
            return 1, cleaned, [(path, f"failed to remove marker: {e}")]

    for path in restore_paths:
        # Restore both the index and the working tree to HEAD.
        _git(repo, "restore", "--staged", "--worktree", "--source=HEAD", "--", path)
        cleaned.append(f"restored bookkeeping-only {path} to HEAD")

    return 0, cleaned, refused


def main():
    parser = argparse.ArgumentParser(
        description="Deterministically clean KNOWN worktree-dispatch leak-class "
                    "noise from the main tree before merge: restore a leaked "
                    "main-HEAD branch switch to the resolved integration target "
                    "(Inv 44 / Inv 61 / #596) FIRST, then "
                    "remove stray .rabbit-scope-active-* markers and revert "
                    "bookkeeping-only feature.json edits (Inv 43 / #583). Fails "
                    "loudly on any unexpected tracked change, a dirty/un-pushed "
                    "leaked branch, etc.; never discards it."
    )
    parser.parse_args()

    repo = _repo_root()
    code, cleaned, refused = clean(repo)

    if refused:
        sys.stderr.write(
            "clean-dispatch-leaks: REFUSING — unexpected tracked "
            "modification(s) found; aborting without discarding them:\n"
        )
        for path, reason in refused:
            sys.stderr.write(f"  {path}: {reason}\n")
        _log("dispatch-leak cleanup refused",
             "; ".join(f"{p} ({r})" for p, r in refused))
        return code

    for desc in cleaned:
        sys.stderr.write(f"clean-dispatch-leaks: {desc}\n")
    if cleaned:
        _log("dispatch-leak cleanup", "; ".join(cleaned))

    json.dump({"status": "clean", "cleaned": cleaned}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
