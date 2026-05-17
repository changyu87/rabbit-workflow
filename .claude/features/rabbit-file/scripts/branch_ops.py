#!/usr/bin/env python3
"""
branch_ops.py — all git operations against origin/bug-backlog-files.

Uses a git worktree at .claude/tmp/bug-backlog-files (gitignored).
Auto-initializes the orphan branch on first use.
"""

import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

_BRANCH = "bug-backlog-files"
_WT_REL = ".claude/tmp/bug-backlog-files"


def _get_repo_root() -> str:
    """Return the git repo root. Called lazily at use sites."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git rev-parse --show-toplevel failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _git(repo, *args):
    """Run git inside repo. Returns stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {repo}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _branch_exists_on_remote(repo_root):
    """Return True if origin/bug-backlog-files exists."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-remote", "--heads",
         "origin", _BRANCH],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ls-remote failed: {result.stderr.strip()}")
    return bool(result.stdout.strip())


def _init_orphan_branch(repo_root):
    """Create origin/bug-backlog-files as an orphan branch with an empty root commit."""
    tmp = Path(repo_root) / ".claude" / "tmp" / "branch-init-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        subprocess.run(["git", "init", str(tmp)], check=True, capture_output=True)
        _git(tmp, "config", "user.email", "rabbit-file@localhost")
        _git(tmp, "config", "user.name", "rabbit-file")
        _git(tmp, "checkout", "--orphan", _BRANCH)
        # Empty commit (no files staged)
        subprocess.run(
            ["git", "-C", str(tmp), "commit", "--allow-empty",
             "-m", "init: orphan branch"],
            check=True, capture_output=True
        )
        # Push to the real origin
        origin_url = _git(repo_root, "remote", "get-url", "origin")
        _git(tmp, "remote", "add", "origin", origin_url)
        _git(tmp, "push", "origin", f"HEAD:{_BRANCH}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _ensure_branch(repo_root):
    """Ensure origin/bug-backlog-files exists; create it if not."""
    if not _branch_exists_on_remote(repo_root):
        _init_orphan_branch(repo_root)


@contextmanager
def _worktree(repo_root):
    """
    Context manager: set up git worktree at .claude/tmp/bug-backlog-files,
    yield the Path, always clean up in finally.
    """
    _ensure_branch(repo_root)

    wt = Path(repo_root) / _WT_REL
    wt.parent.mkdir(parents=True, exist_ok=True)

    # Remove stale worktree if present
    if wt.exists():
        shutil.rmtree(wt)
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "prune"],
        capture_output=True
    )

    # Fetch latest from remote so we track the current tip
    subprocess.run(
        ["git", "-C", str(repo_root), "fetch", "origin", _BRANCH],
        check=True, capture_output=True
    )

    # Add the worktree tracking origin/bug-backlog-files
    _git(repo_root, "worktree", "add", str(wt),
         f"origin/{_BRANCH}", "--no-checkout")

    try:
        # Unconditionally reset the local tracking branch to the freshly-fetched
        # remote tip. Capital -B is mandatory: it eliminates stale-read failures
        # (BUG-4) and non-fast-forward push failures (BUG-5). The earlier
        # two-step try/checkout-local + fallback checkout-b sequence is
        # forbidden by spec invariant.
        subprocess.run(
            ["git", "-C", str(wt), "checkout", "-B",
             _BRANCH, f"origin/{_BRANCH}"],
            check=True, capture_output=True
        )

        # Configure identity inside worktree
        _git(wt, "config", "user.email", "rabbit-file@localhost")
        _git(wt, "config", "user.name", "rabbit-file")

        yield wt
    finally:
        shutil.rmtree(wt, ignore_errors=True)
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "prune"],
            capture_output=True
        )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def counter_path(wt: Path, feature: str, type_: str) -> Path:
    """Return Path to counter.json for feature+type_, creating parent dirs."""
    folder = _type_folder(type_)
    p = wt / "rabbit" / "features" / feature / folder / "counter.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _item_dir(wt: Path, feature: str, type_: str, id_str: str) -> Path:
    folder = _type_folder(type_)
    return wt / "rabbit" / "features" / feature / folder / id_str


def _type_folder(type_: str) -> str:
    return f"{type_}s"  # "bug" -> "bugs", "backlog" -> "backlogs"


# ---------------------------------------------------------------------------
# Counter operations
# ---------------------------------------------------------------------------

def read_counter(wt: Path, feature: str, type_: str) -> int:
    """Read {"next": N} from counter.json. Returns 1 if file missing."""
    cp = counter_path(wt, feature, type_)
    if not cp.exists():
        return 1
    data = json.loads(cp.read_text())
    return data.get("next", 1)


def write_counter(wt: Path, feature: str, type_: str, n: int) -> None:
    """Write {"next": n} to counter.json."""
    cp = counter_path(wt, feature, type_)
    cp.write_text(json.dumps({"next": n}))


# ---------------------------------------------------------------------------
# ID formatting
# ---------------------------------------------------------------------------

def _format_id(feature: str, type_: str, n: int) -> str:
    """e.g. feature="rabbit-cage", type_="bug", n=17 -> "RABBIT-CAGE-BUG-17"."""
    feature_upper = feature.upper()
    type_upper = type_.upper()
    return f"{feature_upper}-{type_upper}-{n}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def allocate_id(feature: str, type_: str) -> str:
    """
    Allocate next ID for feature+type_:
    - Opens worktree
    - Reads counter N (default 1 if missing)
    - Writes N+1
    - Commits "counter: reserve <ID>" and pushes
    - Returns id_str e.g. "RABBIT-CAGE-BUG-17"
    """
    repo_root = _get_repo_root()
    with _worktree(repo_root) as wt:
        n = read_counter(wt, feature, type_)
        id_str = _format_id(feature, type_, n)
        write_counter(wt, feature, type_, n + 1)

        cp = counter_path(wt, feature, type_)
        _git(wt, "add", str(cp.relative_to(wt)))
        _git(wt, "commit", "-m", f"counter: reserve {id_str}")
        _git(wt, "push", "origin", f"HEAD:{_BRANCH}")

    return id_str


def commit_item(feature: str, type_: str, id_str: str, item: dict) -> str:
    """
    Write item.json under rabbit/features/<feature>/<type_>s/<id_str>/item.json,
    commit "item: <id_str>", push, backfill commit_sha, commit "sha: backfill <id_str>", push.
    Returns the commit SHA.
    """
    repo_root = _get_repo_root()
    with _worktree(repo_root) as wt:
        item_dir = _item_dir(wt, feature, type_, id_str)
        item_dir.mkdir(parents=True, exist_ok=True)
        item_file = item_dir / "item.json"
        item_file.write_text(json.dumps(item, indent=2))

        rel = str(item_file.relative_to(wt))
        _git(wt, "add", rel)
        _git(wt, "commit", "-m", f"item: {id_str}")
        _git(wt, "push", "origin", f"HEAD:{_BRANCH}")

        sha = _git(wt, "rev-parse", "HEAD")

        # Backfill commit_sha into item.json without mutating caller's dict
        stored = {**item, "commit_sha": sha}
        item_file.write_text(json.dumps(stored, indent=2))
        _git(wt, "add", rel)
        _git(wt, "commit", "-m", f"sha: backfill {id_str}")
        _git(wt, "push", "origin", f"HEAD:{_BRANCH}")

    return sha


def fetch_item(feature: str, type_: str, id_str: str) -> "dict | None":
    """
    Open worktree, read item.json for id_str.
    Returns dict or None if not found.
    If the branch doesn't exist, returns None.
    """
    repo_root = _get_repo_root()
    if not _branch_exists_on_remote(repo_root):
        return None

    with _worktree(repo_root) as wt:
        item_file = _item_dir(wt, feature, type_, id_str) / "item.json"
        if not item_file.exists():
            return None
        return json.loads(item_file.read_text())


def read_branch(feature: str = None, type_: str = None,
                status: str = None) -> "list[dict]":
    """
    Walk all item.json under rabbit/features/, filter by feature/type_/status.
    Returns list[dict]. Returns [] if branch doesn't exist.
    """
    repo_root = _get_repo_root()
    if not _branch_exists_on_remote(repo_root):
        return []

    results = []
    with _worktree(repo_root) as wt:
        base = wt / "rabbit" / "features"
        if not base.exists():
            return results

        for item_file in base.rglob("item.json"):
            try:
                item = json.loads(item_file.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            if feature is not None and item.get("related_feature") != feature:
                continue
            if type_ is not None and item.get("type") != type_:
                continue
            if status is not None and item.get("status") != status:
                continue

            results.append(item)

    return results
