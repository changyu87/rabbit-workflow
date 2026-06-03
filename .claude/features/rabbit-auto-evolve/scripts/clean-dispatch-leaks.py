#!/usr/bin/env python3
"""clean-dispatch-leaks.py — deterministic, defense-in-depth pre-merge cleanup
of KNOWN worktree-dispatch leak-class noise from the dispatcher's MAIN working
tree (Inv 43 / issue #583).

Worktree-isolated Phase 5 dispatches sometimes leave working-tree noise in the
dispatcher's main tree because a subagent's process cwd is occasionally the
main/shared checkout (not its worktree) when it runs its LOCK / tdd-step
bookkeeping — a harness limitation the cwd-based `_repo_root` fix in #589
reduced but did not eliminate. Left in place, this noise trips safety-check
Inv 5 ("no uncommitted tracked-file modifications"), which makes merge-prs.py
SKIP every PR in the batch.

`run-tick-phases.py run_post_dispatch` invokes this script as the FIRST action
of Phase 6, BEFORE merge-prs.py. The cleanup handles ONLY two known leak
classes and FAILS LOUDLY on anything else:

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
observable. On a clean tree the script is a no-op (exit 0, nothing logged).

Resolution:
  - repo root via `RABBIT_AUTO_EVOLVE_REPO_ROOT`, else `git rev-parse
    --show-toplevel` from the cwd, else `os.getcwd()`.
  - state dir (for the tick log) via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else
    `<repo_root>/.rabbit` (matching tick-log.py's resolution when run with
    cwd == repo root).

Exit code: 0 on a successful cleanup or no-op; non-zero on unexpected dirt
(reported on stderr) or a git failure. The script never discards an
unexpected change.

Version: 1.0.0
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
                    "noise (stray .rabbit-scope-active-* markers and "
                    "bookkeeping-only feature.json edits) from the main tree "
                    "before merge (Inv 43 / #583). Fails loudly on any "
                    "unexpected tracked change; never discards it."
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
