#!/usr/bin/env python3
"""
branch_ops.py — all git operations against origin/bug-backlog-files.

Uses a unique per-process git worktree at .claude/tmp/bug-backlog-files-<pid>
(gitignored). Auto-initializes the orphan branch on first use.

Each process gets its own isolated worktree path so concurrent invocations
from different agents do not collide on the same filesystem path
(RABBIT-FILE-BUG-18).
"""

import json
import os
import random
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# ---------------------------------------------------------------------------
# Public module-level constants (BACKLOG-10)
# ---------------------------------------------------------------------------
# Branch name on origin where every bug/backlog item is stored.
BRANCH = "bug-backlog-files"
# Git identity used for every commit produced by this module. Set via env
# vars per-commit (see _git_env_with_identity) so concurrent worktrees do
# not race on .git/config.
IDENTITY_NAME = "rabbit-file"
IDENTITY_EMAIL = "rabbit-file@localhost"

# ---------------------------------------------------------------------------
# Per-field length limits and text sanitization (BACKLOG-7)
# ---------------------------------------------------------------------------
# Both file-item.py (filing time) and item-status.py update (mutation time)
# import these constants and helpers so the limits cannot drift between the
# two paths.
MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 10240  # 10 KiB
# ASCII control characters in this set are preserved by sanitize_text; all
# other characters with ord < 0x20 are stripped (e.g. NUL, bell, ESC).
_ALLOWED_CTRL = {"\t", "\n", "\r"}


def sanitize_text(s: str) -> str:
    """Strip ASCII control characters from s, EXCEPT \\t \\n \\r.
    Protects list-items.py output from terminal escape injection."""
    return "".join(c for c in s if c >= " " or c in _ALLOWED_CTRL)


def validate_field_length(name: str, value: str, limit: int) -> None:
    """Raise ValueError naming the field, the limit, and the actual length
    when len(value) > limit."""
    if len(value) > limit:
        raise ValueError(
            f"{name} exceeds max length {limit} (got {len(value)} characters)"
        )
# Spec floor is "at least 3 attempts". Real-world concurrent contention
# from multiple agent worktrees racing on the same remote ref needs more
# headroom (each subprocess does 3 pushes: counter + item + sha-backfill,
# so with N racers there are 3N contesting pushes). Each retry re-fetches
# origin, resets HEAD, re-applies the local change, and uses jittered
# backoff.
_MAX_PUSH_ATTEMPTS = 16


def _worktree_rel() -> str:
    """Per-process worktree path under .claude/tmp/. pid is stable per process."""
    return f".claude/tmp/bug-backlog-files-{os.getpid()}"


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

def _git_env_with_identity():
    """Return env vars that set the git author/committer identity inline,
    avoiding writes to the shared .git/config file. Required for safe
    concurrent operation across per-process worktrees (BUG-18 follow-on).
    """
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = IDENTITY_NAME
    env["GIT_AUTHOR_EMAIL"] = IDENTITY_EMAIL
    env["GIT_COMMITTER_NAME"] = IDENTITY_NAME
    env["GIT_COMMITTER_EMAIL"] = IDENTITY_EMAIL
    return env


def _git(repo, *args):
    """Run git inside repo. Returns stdout. Raises on non-zero exit.
    Identity env vars are always set so commits don't need a configured
    user.name/user.email (which would race on .git/config).
    """
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True,
        env=_git_env_with_identity(),
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
         "origin", BRANCH],
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
        # Identity supplied via env vars in _git; the orphan-init tmp repo
        # is private so we don't bother writing to its config.
        _git(tmp, "checkout", "--orphan", BRANCH)
        # Empty commit (no files staged)
        subprocess.run(
            ["git", "-C", str(tmp), "commit", "--allow-empty",
             "-m", "init: orphan branch"],
            check=True, capture_output=True,
            env=_git_env_with_identity(),
        )
        # Push to the real origin
        origin_url = _git(repo_root, "remote", "get-url", "origin")
        _git(tmp, "remote", "add", "origin", origin_url)
        _git(tmp, "push", "origin", f"HEAD:{BRANCH}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _is_local_origin(repo_root) -> bool:
    """Return True iff origin is a local filesystem path (not a network URL).

    Classification:
      - starts with "/"           -> local
      - starts with "file://"     -> local
      - contains "://"            -> remote (http://, https://, ssh://, git://)
      - starts with "git@"        -> remote (git-over-SSH shorthand)
      - otherwise                 -> local (relative path)

    This is used by _ensure_branch to refuse silent orphan-branch creation
    in chained-workspace topologies (BUG-32): when the immediate origin is
    another local repo, a missing branch may exist further upstream and
    must not be overwritten by a fresh local orphan.
    """
    origin_url = _git(repo_root, "remote", "get-url", "origin")
    if origin_url.startswith("/"):
        return True
    if origin_url.startswith("file://"):
        return True
    if "://" in origin_url:
        return False
    if origin_url.startswith("git@"):
        return False
    return True


def _ensure_branch(repo_root):
    """Ensure origin/bug-backlog-files exists; create it if not.

    BUG-32: when origin is a local filesystem path and the branch is not
    found, refuse to bootstrap an orphan. In a chained-workspace topology
    the upstream branch may exist genuinely further up the chain but be
    absent from the intermediate's refs/heads/. Silent orphan creation
    would push an empty branch to the intermediate and later overwrite
    legitimate upstream items. Operator must materialize the branch in
    the intermediate first.
    """
    if _branch_exists_on_remote(repo_root):
        return
    if _is_local_origin(repo_root):
        origin_url = _git(repo_root, "remote", "get-url", "origin")
        raise RuntimeError(
            f"rabbit-file: refusing to create orphan branch "
            f"{BRANCH!r} against local origin {origin_url!r}.\n"
            f"This looks like a chained-workspace topology where the "
            f"branch may exist further upstream but is missing from the "
            f"intermediate's refs/heads/. Silently bootstrapping an orphan "
            f"would later overwrite the legitimate upstream items.\n"
            f"Remediation: materialize the branch in the intermediate first:\n"
            f"  git -C {origin_url} fetch origin {BRANCH} && "
            f"git -C {origin_url} checkout {BRANCH}\n"
            f"Then retry the rabbit-file operation from this workspace."
        )
    _init_orphan_branch(repo_root)


@contextmanager
def _worktree(repo_root):
    """
    Context manager: set up git worktree at .claude/tmp/bug-backlog-files,
    yield the Path, always clean up in finally.
    """
    _ensure_branch(repo_root)

    wt = Path(repo_root) / _worktree_rel()
    wt.parent.mkdir(parents=True, exist_ok=True)

    # Remove stale worktree if present
    if wt.exists():
        shutil.rmtree(wt)
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "prune"],
        capture_output=True
    )

    # Fetch latest from remote so we track the current tip. Retry on
    # transient .git lock contention from concurrent worktrees.
    _run_git_with_lock_retry(
        ["git", "-C", str(repo_root), "fetch", "origin", BRANCH])

    # Add the worktree with HEAD detached at origin/bug-backlog-files.
    # Detached HEAD avoids the cross-worktree branch-checkout collision that
    # otherwise occurs when concurrent per-process worktrees all try to
    # check out the same local branch ref (only one worktree may hold a
    # given branch at a time). All pushes use the refspec
    # HEAD:bug-backlog-files (see _commit_and_push_with_retry). Retry on
    # transient .git lock contention.
    _run_git_with_lock_retry(
        ["git", "-C", str(repo_root), "worktree", "add", "--detach",
         str(wt), f"origin/{BRANCH}"])

    try:
        # Identity is supplied per-commit via env vars (see _git_env_with_identity)
        # instead of `git config` so concurrent worktrees do not race on the
        # shared .git/config file lock.
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
    """Return Path to counter.json for feature+type_, creating parent dirs.
    type_ "bug" maps to folder "bugs"; "backlog" maps to "backlogs"."""
    p = wt / "rabbit" / "features" / feature / f"{type_}s" / "counter.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _item_dir(wt: Path, feature: str, type_: str, id_str: str) -> Path:
    return wt / "rabbit" / "features" / feature / f"{type_}s" / id_str


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
# Push retry (BUG-20)
# ---------------------------------------------------------------------------

def _is_retryable_push_error(stderr: str) -> bool:
    """True for non-fast-forward AND transient remote ref-lock contention.
    Both surface under concurrent pushers to the same remote branch and
    are resolved by the same fetch+reset+reapply loop.
    """
    s = (stderr or "").lower()
    return (
        "non-fast-forward" in s
        or "fetch first" in s
        or "rejected" in s
        or "cannot lock ref" in s
        or "failed to update ref" in s
    )


def _run_git_with_lock_retry(cmd, max_attempts: int = 5):
    """Run a git subprocess command, retrying on transient `.git/refs` or
    `.git/index.lock` contention that arises when concurrent worktrees
    operate on the same underlying repo. Distinct from the push-retry loop
    above: this handles LOCAL git lock contention, not REMOTE push rejection.
    """
    last_err = None
    for attempt in range(1, max_attempts + 1):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result
        last_err = result.stderr or ""
        lower = last_err.lower()
        is_lock_race = (
            "unable to create" in lower and ".lock" in lower
            or "cannot lock" in lower
            or "index.lock" in lower
            or "could not lock" in lower
        )
        if not is_lock_race or attempt == max_attempts:
            raise RuntimeError(
                f"git command {' '.join(str(c) for c in cmd)} failed "
                f"(returncode={result.returncode}): {last_err.strip()}"
            )
        time.sleep(random.uniform(0.05, 0.3) * attempt)


def _reset_worktree_to_origin(wt: Path) -> None:
    """Re-fetch and hard-reset the worktree to the freshly-fetched remote tip
    in detached-HEAD mode. Used by the push-retry path to rebase local state
    on top of the competing commit that caused the non-fast-forward failure.
    Detached HEAD keeps per-process worktrees from colliding on the shared
    local branch ref. All git invocations retry on transient .git lock
    contention (concurrent worktrees can race on .git/refs and .git/index).
    """
    _run_git_with_lock_retry(
        ["git", "-C", str(wt), "fetch", "origin", BRANCH])
    _run_git_with_lock_retry(
        ["git", "-C", str(wt), "checkout", "--detach", f"origin/{BRANCH}"])
    _run_git_with_lock_retry(
        ["git", "-C", str(wt), "reset", "--hard", f"origin/{BRANCH}"])


def _commit_and_push_with_retry(wt: Path, stage_and_commit_fn,
                                max_attempts: int = _MAX_PUSH_ATTEMPTS):
    """
    Run stage_and_commit_fn(wt) (which must add+commit local changes), then
    push. On non-fast-forward, fetch+reset the worktree branch and re-invoke
    stage_and_commit_fn to re-apply changes against the fresh tip. Retry up
    to max_attempts times. Raises RuntimeError on exhaustion.

    stage_and_commit_fn(wt) must be idempotent against a clean tree: each
    invocation re-derives the desired state (e.g. re-reads counter.json,
    re-allocates ID if taken, re-writes the file, stages, commits).
    """
    last_stderr = ""
    for attempt in range(1, max_attempts + 1):
        stage_and_commit_fn(wt)
        push = subprocess.run(
            ["git", "-C", str(wt), "push", "origin", f"HEAD:{BRANCH}"],
            capture_output=True, text=True,
        )
        if push.returncode == 0:
            return
        last_stderr = push.stderr or ""
        if not _is_retryable_push_error(last_stderr):
            raise RuntimeError(
                f"git push failed (non-retryable) in {wt}: {last_stderr.strip()}"
            )
        if attempt == max_attempts:
            break
        # Jittered exponential backoff (capped) to de-correlate concurrent
        # pushers contesting the same remote ref before retrying.
        backoff = min(2.0, 0.05 * (2 ** (attempt - 1))) + random.uniform(0, 0.1)
        time.sleep(backoff)
        # Reset to fresh remote tip; next iteration's stage_and_commit_fn
        # will re-apply the local change on top.
        _reset_worktree_to_origin(wt)
    raise RuntimeError(
        f"git push failed after {max_attempts} attempts (non-fast-forward); "
        f"last error: {last_stderr.strip()}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def allocate_id(feature: str, type_: str) -> str:
    """
    Allocate next ID for feature+type_:
    - Opens worktree
    - Reads counter N (default 1 if missing)
    - Writes N+1
    - Commits "counter: reserve <ID>" and pushes (with retry on
      non-fast-forward; retry re-reads counter so a freshly-reserved slot
      causes us to allocate the next free ID instead).
    - Returns id_str e.g. "RABBIT-CAGE-BUG-17"
    """
    repo_root = _get_repo_root()
    allocated = {"id_str": None}

    def stage_and_commit(wt):
        # Re-read counter on every attempt so retries pick up commits made
        # by competing processes after our reset.
        n = read_counter(wt, feature, type_)
        # ID format: UPPER(feature)-UPPER(type)-N (hyphens preserved verbatim).
        id_str = f"{feature.upper()}-{type_.upper()}-{n}"
        write_counter(wt, feature, type_, n + 1)
        cp = counter_path(wt, feature, type_)
        _git(wt, "add", str(cp.relative_to(wt)))
        # Include pid + nonce in the commit message so two concurrent
        # processes that race to reserve the same ID with identical
        # parent+tree+author do not produce byte-identical commit SHAs
        # (which git push would silently accept as a no-op fast-forward,
        # letting both processes believe they reserved the same ID).
        nonce = f"{os.getpid()}-{random.randint(0, 1 << 30)}"
        _git(wt, "commit", "-m", f"counter: reserve {id_str} [{nonce}]")
        allocated["id_str"] = id_str

    with _worktree(repo_root) as wt:
        _commit_and_push_with_retry(wt, stage_and_commit)

    return allocated["id_str"]


def commit_item(feature: str, type_: str, id_str: str, item: dict) -> str:
    """
    Write item.json under rabbit/features/<feature>/<type_>s/<id_str>/item.json,
    commit "item: <id_str>", push, backfill commit_sha, commit
    "sha: backfill <id_str>", push. Both pushes use the retry helper to
    survive non-fast-forward (BUG-20). Returns the final commit SHA.

    The caller-supplied `item` dict is treated as input-only and is NOT
    mutated by this call (BACKLOG-4): commit_sha is added to an internal
    copy before being persisted, so callers can safely re-use their dict
    for retry or logging.
    """
    repo_root = _get_repo_root()
    sha_holder = {"sha": None}
    # Work against a local copy so the caller's dict is never mutated.
    item_copy = dict(item)

    def stage_item(wt):
        item_dir = _item_dir(wt, feature, type_, id_str)
        item_dir.mkdir(parents=True, exist_ok=True)
        item_file = item_dir / "item.json"
        item_file.write_text(json.dumps(item_copy, indent=2))
        rel = str(item_file.relative_to(wt))
        _git(wt, "add", rel)
        _git(wt, "commit", "-m", f"item: {id_str}")

    def stage_sha_backfill(wt):
        item_dir = _item_dir(wt, feature, type_, id_str)
        item_dir.mkdir(parents=True, exist_ok=True)
        item_file = item_dir / "item.json"
        stored = {**item_copy, "commit_sha": sha_holder["sha"]}
        item_file.write_text(json.dumps(stored, indent=2))
        rel = str(item_file.relative_to(wt))
        _git(wt, "add", rel)
        _git(wt, "commit", "-m", f"sha: backfill {id_str}")

    with _worktree(repo_root) as wt:
        _commit_and_push_with_retry(wt, stage_item)
        sha_holder["sha"] = _git(wt, "rev-parse", "HEAD")
        _commit_and_push_with_retry(wt, stage_sha_backfill)

    return sha_holder["sha"]


def release_id(feature: str, type_: str, id_str: str) -> bool:
    """Best-effort rollback of an allocated-but-unused ID slot (BUG-10).

    If counter.json's `next` value still equals the just-allocated N+1 (i.e.
    no other process has allocated above us), decrement it back to N and
    push the rollback commit. Otherwise leave the counter alone — the slot
    has been overtaken by a competing allocation and reusing it would
    create a duplicate ID.

    Returns True if the slot was reclaimed; False if left alone.
    """
    # Recover N from the trailing "-N" of id_str.
    try:
        n_reserved = int(id_str.rsplit("-", 1)[1])
    except (ValueError, IndexError):
        return False

    repo_root = _get_repo_root()
    released = {"ok": False}

    def stage_rollback(wt):
        cur = read_counter(wt, feature, type_)
        # Safe to roll back only if counter is exactly one past our reserved N.
        if cur != n_reserved + 1:
            # Slot already consumed by another allocation. No rollback.
            return None  # signal "nothing to commit"
        write_counter(wt, feature, type_, n_reserved)
        cp = counter_path(wt, feature, type_)
        _git(wt, "add", str(cp.relative_to(wt)))
        nonce = f"{os.getpid()}-{random.randint(0, 1 << 30)}"
        _git(wt, "commit", "-m", f"counter: release {id_str} [{nonce}]")
        released["ok"] = True

    with _worktree(repo_root) as wt:
        # Custom retry: if stage_rollback decides not to commit (slot overtaken),
        # we abort without pushing.
        for attempt in range(1, _MAX_PUSH_ATTEMPTS + 1):
            result = stage_rollback(wt)
            if result is None and not released["ok"]:
                # Nothing to commit — slot was overtaken.
                return False
            push = subprocess.run(
                ["git", "-C", str(wt), "push", "origin", f"HEAD:{BRANCH}"],
                capture_output=True, text=True,
            )
            if push.returncode == 0:
                return True
            if not _is_retryable_push_error(push.stderr or ""):
                # Non-retryable push error during rollback — best-effort, give up.
                return False
            if attempt == _MAX_PUSH_ATTEMPTS:
                return False
            backoff = min(2.0, 0.05 * (2 ** (attempt - 1))) + random.uniform(0, 0.1)
            time.sleep(backoff)
            _reset_worktree_to_origin(wt)
            released["ok"] = False
    return False


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


def branch_exists() -> bool:
    """Return True iff origin/bug-backlog-files exists. Public helper
    for callers that need to distinguish 'no branch' from 'branch exists
    but no matching items' (BUG-28)."""
    return _branch_exists_on_remote(_get_repo_root())


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
            except (json.JSONDecodeError, OSError) as err:
                # BUG-24: never silently swallow malformed items. Log a
                # structured warning that names the offending file (relative
                # to the worktree root, with the containing ID dir) and the
                # underlying parse/IO error class. Operators need to see
                # corruption when it happens.
                try:
                    rel = item_file.relative_to(wt)
                except ValueError:
                    rel = item_file
                # Surface the item-dir name (ID) prominently in the message
                # so it can be grepped/diagnosed quickly.
                id_dir = item_file.parent.name
                sys.stderr.write(
                    f"rabbit-file: malformed item.json skipped: "
                    f"{rel} (id={id_dir}): {type(err).__name__}: {err}\n"
                )
                continue

            if feature is not None and item.get("related_feature") != feature:
                continue
            if type_ is not None and item.get("type") != type_:
                continue
            if status is not None and item.get("status") != status:
                continue

            results.append(item)

    return results
