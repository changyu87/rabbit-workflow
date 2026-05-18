#!/usr/bin/env python3
"""
E2E test for branch_ops._worktree() fresh-checkout invariant.

Spec invariant under test:
  branch_ops._worktree() MUST check out the worktree branch using
  `git checkout -B bug-backlog-files origin/bug-backlog-files` (capital -B)
  after fetching origin/bug-backlog-files. This unconditionally resets the
  local tracking branch to the freshly-fetched remote tip. The fallback
  two-step try/checkout-local + checkout-b sequence MUST NOT be used.

Failure mode reproduced:
  - Local `bug-backlog-files` branch points at an older commit (stale).
  - origin/bug-backlog-files has a newer commit committed by another actor.
  - Under the previous two-step fallback, `git checkout bug-backlog-files`
    succeeds and the worktree HEAD remains stale — reads miss the new commit
    and the next push is non-fast-forward.
  - Under `checkout -B bug-backlog-files origin/bug-backlog-files`, the
    local tracking branch is unconditionally reset to the freshly-fetched
    remote tip, eliminating both failure modes.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FEATURE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = FEATURE_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import branch_ops  # noqa: E402


def _git(repo, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args} failed: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture()
def isolated_repo(tmp_path):
    """Isolated bare-remote + working clone, matches harness in test-branch-ops.py."""
    remote = tmp_path / "remote"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                   capture_output=True)

    local = tmp_path / "local"
    subprocess.run(["git", "clone", str(remote), str(local)], check=True,
                   capture_output=True)

    _git(local, "config", "user.email", "test@test.invalid")
    _git(local, "config", "user.name", "Test")

    (local / "README").write_text("init")
    _git(local, "add", ".")
    _git(local, "commit", "-m", "init")
    _git(local, "push", "origin", "HEAD:main")

    yield local

    tmp_dir = local / ".claude" / "tmp"
    if tmp_dir.exists():
        for child in tmp_dir.iterdir():
            if child.name.startswith("bug-backlog-files"):
                shutil.rmtree(child, ignore_errors=True)
    subprocess.run(["git", "-C", str(local), "worktree", "prune"],
                   capture_output=True)


@pytest.fixture(autouse=True)
def patch_repo_root(isolated_repo, monkeypatch):
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))


def _origin_tip(repo, branch):
    """SHA of origin/<branch> as currently fetched."""
    subprocess.run(
        ["git", "-C", str(repo), "fetch", "origin", branch],
        check=True, capture_output=True
    )
    return _git(repo, "rev-parse", f"origin/{branch}")


def _local_branch_sha(repo, branch):
    """SHA of local <branch> (None if branch missing)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", branch],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _simulate_concurrent_remote_commit(isolated_repo):
    """
    Simulate another actor pushing a new commit to origin/bug-backlog-files
    while we hold a stale local branch.

    Returns the new origin tip SHA.
    """
    remote_url = _git(isolated_repo, "remote", "get-url", "origin")
    other = isolated_repo.parent / "other-clone"
    if other.exists():
        shutil.rmtree(other)
    subprocess.run(
        ["git", "clone", "--branch", "bug-backlog-files",
         remote_url, str(other)],
        check=True, capture_output=True
    )
    _git(other, "config", "user.email", "other@test.invalid")
    _git(other, "config", "user.name", "Other")
    (other / "concurrent-commit-marker.txt").write_text("from other actor")
    _git(other, "add", "concurrent-commit-marker.txt")
    _git(other, "commit", "-m", "concurrent: simulated remote commit")
    _git(other, "push", "origin", "HEAD:bug-backlog-files")
    new_tip = _git(other, "rev-parse", "HEAD")
    shutil.rmtree(other, ignore_errors=True)
    return new_tip


class TestWorktreeFreshCheckout:
    def test_worktree_head_matches_origin_tip_when_local_branch_is_stale(
            self, isolated_repo):
        """
        Setup: allocate one ID (creates branch and local tracking ref pointing
        at the old tip). Then simulate a concurrent push that advances
        origin/bug-backlog-files past the local ref. Calling _worktree() again
        must reset to the fresh origin tip, not the stale local tip.
        """
        # 1. First allocation initialises branch + local tracking ref.
        branch_ops.allocate_id("rabbit-cage", "bug")
        stale_local = _local_branch_sha(isolated_repo, "bug-backlog-files")
        assert stale_local is not None, "local tracking branch must exist after first use"

        # 2. Another actor pushes a new commit to origin/bug-backlog-files.
        new_origin_tip = _simulate_concurrent_remote_commit(isolated_repo)
        assert new_origin_tip != stale_local, "simulated concurrent push must advance origin"

        # 3. Confirm local tracking ref is now stale relative to origin.
        assert _local_branch_sha(isolated_repo, "bug-backlog-files") == stale_local

        # 4. Enter _worktree() again. With the spec-mandated `checkout -B`,
        #    the worktree HEAD must equal the freshly-fetched origin tip.
        with branch_ops._worktree(str(isolated_repo)) as wt:
            wt_head = _git(wt, "rev-parse", "HEAD")
            assert wt_head == new_origin_tip, (
                f"worktree HEAD={wt_head} does not match "
                f"origin/bug-backlog-files tip={new_origin_tip}; "
                f"stale local tip was {stale_local}"
            )

    def test_concurrent_remote_commit_visible_to_reads(self, isolated_repo):
        """
        End-to-end: when origin has items committed by another actor after our
        last operation, fetch_item / read_branch must see them. Previously,
        a stale local branch caused reads to silently miss new items (BUG-4).
        """
        # 1. Allocate + commit an item locally so the branch is established.
        local_id = branch_ops.allocate_id("rabbit-cage", "bug")
        item = {
            "name": local_id, "type": "bug", "title": "local",
            "status": "open", "priority": "low", "description": "x",
            "related_feature": "rabbit-cage",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "tester",
            "closed": None, "history": [],
        }
        branch_ops.commit_item("rabbit-cage", "bug", local_id, item)

        # 2. Another actor commits a new item directly to origin.
        remote_url = _git(isolated_repo, "remote", "get-url", "origin")
        other = isolated_repo.parent / "other-clone-reads"
        if other.exists():
            shutil.rmtree(other)
        subprocess.run(
            ["git", "clone", "--branch", "bug-backlog-files",
             remote_url, str(other)],
            check=True, capture_output=True
        )
        _git(other, "config", "user.email", "other@test.invalid")
        _git(other, "config", "user.name", "Other")
        other_dir = (other / "rabbit" / "features" / "rabbit-cage"
                     / "bugs" / "RABBIT-CAGE-BUG-999")
        other_dir.mkdir(parents=True, exist_ok=True)
        other_item = {
            "name": "RABBIT-CAGE-BUG-999", "type": "bug",
            "title": "from other actor", "status": "open",
            "priority": "high", "description": "remote",
            "related_feature": "rabbit-cage",
            "filed": "2026-01-02T00:00:00Z", "filed_by": "other",
            "closed": None, "history": [],
        }
        (other_dir / "item.json").write_text(json.dumps(other_item, indent=2))
        _git(other, "add", str(other_dir / "item.json"))
        _git(other, "commit", "-m", "item: RABBIT-CAGE-BUG-999 (from other)")
        _git(other, "push", "origin", "HEAD:bug-backlog-files")
        shutil.rmtree(other, ignore_errors=True)

        # 3. Local fetch_item must see the remote item without any cache flush.
        fetched = branch_ops.fetch_item(
            "rabbit-cage", "bug", "RABBIT-CAGE-BUG-999")
        assert fetched is not None, (
            "fetch_item could not see concurrent remote commit; "
            "_worktree did not reset to fresh origin tip"
        )
        assert fetched["title"] == "from other actor"

    def test_writes_do_not_fail_with_non_fast_forward(self, isolated_repo):
        """
        End-to-end: after a concurrent remote commit, the next write must
        succeed (not non-fast-forward), because _worktree() rebased on
        the fresh origin tip via checkout -B. (BUG-5.)
        """
        branch_ops.allocate_id("rabbit-cage", "bug")
        _simulate_concurrent_remote_commit(isolated_repo)

        # Next allocate_id must NOT raise non-fast-forward.
        id2 = branch_ops.allocate_id("rabbit-cage", "bug")
        assert id2  # successfully allocated


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
