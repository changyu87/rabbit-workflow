#!/usr/bin/env python3
"""
Tests for branch_ops.py — isolated temp-git-repo harness.
All git operations run against a local bare repo (no real remote needed).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Locate branch_ops relative to this file's feature root
FEATURE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = FEATURE_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import branch_ops  # noqa: E402 — must be after sys.path insert


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _git(repo, *args, **kwargs):
    """Run a git command inside repo, return stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True, **kwargs
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {args} failed: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture()
def isolated_repo(tmp_path):
    """
    Create an isolated git environment:
      tmp_path/remote  — bare repo acting as 'origin'
      tmp_path/local   — working clone; branch_ops uses this as repo_root
    Returns the local repo Path.
    """
    remote = tmp_path / "remote"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                   capture_output=True)

    local = tmp_path / "local"
    subprocess.run(["git", "clone", str(remote), str(local)], check=True,
                   capture_output=True)

    # Minimal git identity inside local
    _git(local, "config", "user.email", "test@test.invalid")
    _git(local, "config", "user.name", "Test")

    # Make an initial commit on main so HEAD exists
    (local / "README").write_text("init")
    _git(local, "add", ".")
    _git(local, "commit", "-m", "init")
    _git(local, "push", "origin", "HEAD:main")

    yield local

    # Clean up any per-process worktree that tests may have left under
    # .claude/tmp/bug-backlog-files-<pid>. The legacy fixed path
    # .claude/tmp/bug-backlog-files is no longer used.
    tmp_dir = local / ".claude" / "tmp"
    if tmp_dir.exists():
        for child in tmp_dir.iterdir():
            if child.name.startswith("bug-backlog-files"):
                shutil.rmtree(child, ignore_errors=True)
    subprocess.run(["git", "-C", str(local), "worktree", "prune"],
                   capture_output=True)


# ---------------------------------------------------------------------------
# Helper: monkey-patch repo_root inside branch_ops
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_repo_root(isolated_repo, monkeypatch):
    """Make branch_ops use the isolated repo instead of the real one."""
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))


# ---------------------------------------------------------------------------
# Tests: allocate_id
# ---------------------------------------------------------------------------

class TestAllocateId:
    def test_first_call_returns_correct_format_bug(self, isolated_repo):
        id_str = branch_ops.allocate_id("rabbit-cage", "bug")
        assert id_str == "RABBIT-CAGE-BUG-1"

    def test_first_call_returns_correct_format_backlog(self, isolated_repo):
        id_str = branch_ops.allocate_id("rabbit-cage", "backlog")
        assert id_str == "RABBIT-CAGE-BACKLOG-1"

    def test_second_call_increments(self, isolated_repo):
        id1 = branch_ops.allocate_id("rabbit-cage", "bug")
        id2 = branch_ops.allocate_id("rabbit-cage", "bug")
        assert id1 == "RABBIT-CAGE-BUG-1"
        assert id2 == "RABBIT-CAGE-BUG-2"

    def test_different_type_independent_counter(self, isolated_repo):
        bug_id = branch_ops.allocate_id("my-feature", "bug")
        backlog_id = branch_ops.allocate_id("my-feature", "backlog")
        assert bug_id == "MY-FEATURE-BUG-1"
        assert backlog_id == "MY-FEATURE-BACKLOG-1"

    def test_different_feature_independent_counter(self, isolated_repo):
        id_a = branch_ops.allocate_id("feature-a", "bug")
        id_b = branch_ops.allocate_id("feature-b", "bug")
        assert id_a == "FEATURE-A-BUG-1"
        assert id_b == "FEATURE-B-BUG-1"

    def test_counter_persists_across_calls(self, isolated_repo):
        for _ in range(3):
            branch_ops.allocate_id("persist-feature", "bug")
        id4 = branch_ops.allocate_id("persist-feature", "bug")
        assert id4 == "PERSIST-FEATURE-BUG-4"

    def test_branch_auto_initialized(self, isolated_repo):
        """Bootstrap-on-first-use: allocate_id against a fresh standalone
        remote (no pre-existing bug-backlog-files branch) auto-creates the
        orphan branch. BACKLOG-12: no topology guard sits between the
        caller and _init_orphan_branch."""
        # The remote is bare and has no bug-backlog-files branch.
        result = subprocess.run(
            ["git", "-C", str(isolated_repo), "ls-remote", "--heads",
             "origin", "bug-backlog-files"],
            capture_output=True, text=True
        )
        assert result.stdout.strip() == ""

        branch_ops.allocate_id("rabbit-cage", "bug")

        # Now it should exist on the remote.
        result = subprocess.run(
            ["git", "-C", str(isolated_repo), "ls-remote", "--heads",
             "origin", "bug-backlog-files"],
            capture_output=True, text=True
        )
        assert "bug-backlog-files" in result.stdout


# ---------------------------------------------------------------------------
# Tests: commit_item
# ---------------------------------------------------------------------------

class TestCommitItem:
    def test_commit_item_writes_item_json(self, isolated_repo):
        id_str = branch_ops.allocate_id("rabbit-cage", "bug")
        item = {
            "name": id_str,
            "type": "bug",
            "title": "Test bug",
            "status": "open",
            "priority": "high",
            "description": "A test bug",
            "related_feature": "rabbit-cage",
            "filed": "2026-01-01T00:00:00Z",
            "filed_by": "tester",
            "closed": None,
            "history": [],
        }
        sha = branch_ops.commit_item("rabbit-cage", "bug", id_str, item)
        assert sha  # non-empty SHA

    def test_commit_item_backfills_commit_sha(self, isolated_repo):
        id_str = branch_ops.allocate_id("rabbit-cage", "bug")
        item = {
            "name": id_str,
            "type": "bug",
            "title": "SHA backfill test",
            "status": "open",
            "priority": "low",
            "description": "checks sha backfill",
            "related_feature": "rabbit-cage",
            "filed": "2026-01-01T00:00:00Z",
            "filed_by": "tester",
            "closed": None,
            "history": [],
        }
        sha = branch_ops.commit_item("rabbit-cage", "bug", id_str, item)

        # Read back the item from the branch and verify commit_sha is present
        fetched = branch_ops.fetch_item("rabbit-cage", "bug", id_str)
        assert fetched is not None
        assert fetched.get("commit_sha") == sha

    def test_commit_item_content_matches(self, isolated_repo):
        id_str = branch_ops.allocate_id("rabbit-cage", "bug")
        item = {
            "name": id_str,
            "type": "bug",
            "title": "Content match test",
            "status": "open",
            "priority": "medium",
            "description": "content check",
            "related_feature": "rabbit-cage",
            "filed": "2026-01-01T00:00:00Z",
            "filed_by": "tester",
            "closed": None,
            "history": [],
        }
        branch_ops.commit_item("rabbit-cage", "bug", id_str, item)
        fetched = branch_ops.fetch_item("rabbit-cage", "bug", id_str)
        assert fetched is not None
        assert fetched["title"] == "Content match test"
        assert fetched["status"] == "open"
        assert fetched["priority"] == "medium"


# ---------------------------------------------------------------------------
# Tests: fetch_item
# ---------------------------------------------------------------------------

class TestFetchItem:
    def test_fetch_missing_returns_none(self, isolated_repo):
        # Ensure branch exists first
        branch_ops.allocate_id("rabbit-cage", "bug")
        result = branch_ops.fetch_item("rabbit-cage", "bug", "RABBIT-CAGE-BUG-999")
        assert result is None

    def test_fetch_existing_returns_dict(self, isolated_repo):
        id_str = branch_ops.allocate_id("rabbit-cage", "bug")
        item = {
            "name": id_str,
            "type": "bug",
            "title": "Fetchable item",
            "status": "open",
            "priority": "critical",
            "description": "fetch test",
            "related_feature": "rabbit-cage",
            "filed": "2026-01-01T00:00:00Z",
            "filed_by": "tester",
            "closed": None,
            "history": [],
        }
        branch_ops.commit_item("rabbit-cage", "bug", id_str, item)
        result = branch_ops.fetch_item("rabbit-cage", "bug", id_str)
        assert isinstance(result, dict)
        assert result["name"] == id_str

    def test_fetch_branch_not_exist_returns_none(self, isolated_repo):
        # Don't create the branch — fetch on nonexistent branch must return None
        result = branch_ops.fetch_item("no-such-feature", "bug", "NO-SUCH-FEATURE-BUG-1")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: read_branch
# ---------------------------------------------------------------------------

class TestReadBranch:
    def _file_item(self, feature, type_, title, status, priority="low"):
        id_str = branch_ops.allocate_id(feature, type_)
        item = {
            "name": id_str,
            "type": type_,
            "title": title,
            "status": status,
            "priority": priority,
            "description": "test",
            "related_feature": feature,
            "filed": "2026-01-01T00:00:00Z",
            "filed_by": "tester",
            "closed": None,
            "history": [],
        }
        branch_ops.commit_item(feature, type_, id_str, item)
        return id_str

    def test_read_branch_all(self, isolated_repo):
        self._file_item("feat-a", "bug", "Bug A", "open")
        self._file_item("feat-a", "backlog", "Backlog A", "open")
        self._file_item("feat-b", "bug", "Bug B", "open")
        items = branch_ops.read_branch()
        assert len(items) >= 3

    def test_filter_by_feature(self, isolated_repo):
        self._file_item("feat-x", "bug", "Bug X", "open")
        self._file_item("feat-y", "bug", "Bug Y", "open")
        items = branch_ops.read_branch(feature="feat-x")
        assert all(i["related_feature"] == "feat-x" for i in items)
        assert len(items) == 1

    def test_filter_by_type(self, isolated_repo):
        self._file_item("feat-z", "bug", "Bug Z", "open")
        self._file_item("feat-z", "backlog", "Backlog Z", "open")
        bugs = branch_ops.read_branch(type_="bug")
        assert all(i["type"] == "bug" for i in bugs)
        backlogs = branch_ops.read_branch(type_="backlog")
        assert all(i["type"] == "backlog" for i in backlogs)

    def test_filter_by_status(self, isolated_repo):
        self._file_item("feat-s", "bug", "Open bug", "open")
        closed_id = branch_ops.allocate_id("feat-s", "bug")
        item = {
            "name": closed_id,
            "type": "bug",
            "title": "Closed bug",
            "status": "close",
            "priority": "low",
            "description": "closed",
            "related_feature": "feat-s",
            "filed": "2026-01-01T00:00:00Z",
            "filed_by": "tester",
            "closed": "2026-02-01T00:00:00Z",
            "history": [],
        }
        branch_ops.commit_item("feat-s", "bug", closed_id, item)

        open_items = branch_ops.read_branch(status="open")
        assert all(i["status"] == "open" for i in open_items)
        closed_items = branch_ops.read_branch(status="close")
        assert all(i["status"] == "close" for i in closed_items)

    def test_read_branch_no_branch_returns_empty(self, isolated_repo):
        # branch doesn't exist yet — should return []
        items = branch_ops.read_branch()
        assert items == []


# ---------------------------------------------------------------------------
# Tests: worktree cleanup
# ---------------------------------------------------------------------------

class TestWorktreeCleanup:
    def test_worktree_cleaned_up_on_success(self, isolated_repo):
        pid = os.getpid()
        wt_path = Path(isolated_repo) / ".claude" / "tmp" / f"bug-backlog-files-{pid}"
        branch_ops.allocate_id("cleanup-test", "bug")
        # After allocate_id returns, worktree must not exist
        assert not wt_path.exists(), "worktree was not cleaned up after success"

    def test_worktree_cleaned_up_on_exception(self, isolated_repo, monkeypatch):
        """Even when an exception occurs inside _worktree, the WT is cleaned up."""
        pid = os.getpid()
        wt_path = Path(isolated_repo) / ".claude" / "tmp" / f"bug-backlog-files-{pid}"

        # Patch write_counter to raise after first allocation (forces exception inside with block)
        original_write_counter = branch_ops.write_counter

        call_count = [0]
        def raising_write_counter(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 1:
                raise RuntimeError("simulated failure inside worktree")
            return original_write_counter(*args, **kwargs)

        monkeypatch.setattr(branch_ops, "write_counter", raising_write_counter)

        with pytest.raises(RuntimeError, match="simulated failure"):
            branch_ops.allocate_id("cleanup-fail", "bug")

        assert not wt_path.exists(), "worktree was not cleaned up after exception"


# ---------------------------------------------------------------------------
# Entry point for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
