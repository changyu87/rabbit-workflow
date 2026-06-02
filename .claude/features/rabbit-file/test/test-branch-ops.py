#!/usr/bin/env python3
"""
Tests for branch_ops.py — isolated temp-git-repo harness.
All git operations run against a local bare repo (no real remote needed).
"""

import json
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
    # .claude/tmp/bug-backlog-files-<pid>.
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
# Tests: canonical ID format (UPPER(feature)-UPPER(type)-N)
# ---------------------------------------------------------------------------

class TestCanonicalIdFormat:
    def test_hyphenated_feature_name_preserves_hyphens(self):
        feature, type_, n = "rabbit-cage", "bug", 17
        assert f"{feature.upper()}-{type_.upper()}-{n}" == "RABBIT-CAGE-BUG-17"

    def test_multi_hyphen_feature_name(self):
        feature, type_, n = "my-feature-x", "backlog", 3
        assert f"{feature.upper()}-{type_.upper()}-{n}" == "MY-FEATURE-X-BACKLOG-3"

    def test_unhyphenated_feature_name(self):
        feature, type_, n = "single", "bug", 1
        assert f"{feature.upper()}-{type_.upper()}-{n}" == "SINGLE-BUG-1"

    def test_id_format_documented_in_spec(self):
        spec = (Path(__file__).parent.parent / "docs" / "spec" / "spec.md").read_text()
        assert "UPPER(feature)-UPPER(type)-N" in spec, (
            "spec must document canonical ID format"
        )


# ---------------------------------------------------------------------------
# Tests: module-level constants
# ---------------------------------------------------------------------------

class TestModuleConstants:
    def test_branch_constant_exposed(self):
        assert hasattr(branch_ops, "BRANCH")
        assert branch_ops.BRANCH == "bug-backlog-files"

    def test_identity_constants_exposed(self):
        assert hasattr(branch_ops, "IDENTITY_NAME")
        assert hasattr(branch_ops, "IDENTITY_EMAIL")
        assert branch_ops.IDENTITY_NAME == "rabbit-file"
        assert branch_ops.IDENTITY_EMAIL == "rabbit-file@localhost"

    def test_legacy_underscore_branch_alias_removed(self):
        """The private `_BRANCH` alias must be gone; only the public
        `BRANCH` constant remains."""
        assert hasattr(branch_ops, "BRANCH")
        assert not hasattr(branch_ops, "_BRANCH"), (
            "_BRANCH legacy alias must be deleted"
        )

    def test_module_exports_release_id_and_branch_exists(self):
        """The exposed API includes release_id and branch_exists in addition
        to the four core entry points named in spec.md."""
        assert callable(getattr(branch_ops, "release_id", None))
        assert callable(getattr(branch_ops, "branch_exists", None))


# ---------------------------------------------------------------------------
# Tests: read_branch logs malformed item.json to stderr (no silent skip)
# ---------------------------------------------------------------------------

class TestMalformedJsonLogging:
    def test_read_branch_logs_malformed_item_to_stderr(self, isolated_repo,
                                                       capsys):
        id_str = branch_ops.allocate_id("malformed-feat", "bug")
        item = {
            "name": id_str, "type": "bug", "title": "Valid",
            "status": "open", "priority": "low", "description": "x",
            "related_feature": "malformed-feat",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "tester",
            "closed": None, "history": [],
        }
        branch_ops.commit_item("malformed-feat", "bug", id_str, item)

        remote_url = _git(isolated_repo, "remote", "get-url", "origin")
        sibling = isolated_repo.parent / "sibling-malformed"
        if sibling.exists():
            shutil.rmtree(sibling)
        subprocess.run(
            ["git", "clone", "--branch", "bug-backlog-files",
             remote_url, str(sibling)],
            check=True, capture_output=True,
        )
        try:
            _git(sibling, "config", "user.email", "sib@test.invalid")
            _git(sibling, "config", "user.name", "Sib")
            bad_dir = (sibling / "rabbit" / "features" / "malformed-feat"
                       / "bugs" / "MALFORMED-FEAT-BUG-999")
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "item.json").write_text("{not valid json")
            _git(sibling, "add", str((bad_dir / "item.json").relative_to(sibling)))
            _git(sibling, "commit", "-m", "inject: malformed item.json")
            _git(sibling, "push", "origin", "HEAD:bug-backlog-files")
        finally:
            shutil.rmtree(sibling, ignore_errors=True)

        items = branch_ops.read_branch()
        captured = capsys.readouterr()

        assert any(i["name"] == id_str for i in items), (
            f"valid item should still appear in results: {items}"
        )
        assert not any(i.get("name") == "MALFORMED-FEAT-BUG-999" for i in items)
        assert "MALFORMED-FEAT-BUG-999" in captured.err, (
            f"stderr must name the malformed file path; got: {captured.err!r}"
        )
        assert ("malformed" in captured.err.lower()
                or "json" in captured.err.lower()
                or "decode" in captured.err.lower()
                or "parse" in captured.err.lower()), (
            f"stderr must include a parse diagnostic; got: {captured.err!r}"
        )


# ---------------------------------------------------------------------------
# Tests: commit_item must not mutate the caller-supplied item dict
# ---------------------------------------------------------------------------

class TestCallerDictNotMutated:
    def test_commit_item_does_not_mutate_caller_dict(self, isolated_repo):
        id_str = branch_ops.allocate_id("nomutate-feat", "bug")
        item = {
            "name": id_str, "type": "bug", "title": "T",
            "status": "open", "priority": "low", "description": "D",
            "related_feature": "nomutate-feat",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "t",
            "closed": None, "history": [],
        }
        snapshot = dict(item)
        branch_ops.commit_item("nomutate-feat", "bug", id_str, item)
        assert item == snapshot, (
            f"caller dict was mutated. before={snapshot}, after={item}"
        )
        assert "commit_sha" not in item


# ---------------------------------------------------------------------------
# Tests: read_branch skips corrupted JSON but returns the valid items
# ---------------------------------------------------------------------------

class TestCorruptedJsonSkipReturnsValidItems:
    def test_read_branch_skips_corrupted_returns_valid(self, isolated_repo,
                                                       capsys):
        ids = []
        for i in range(2):
            id_str = branch_ops.allocate_id("corrupt-feat", "bug")
            item = {
                "name": id_str, "type": "bug", "title": f"v{i}",
                "status": "open", "priority": "low", "description": "x",
                "related_feature": "corrupt-feat",
                "filed": "2026-01-01T00:00:00Z", "filed_by": "t",
                "closed": None, "history": [],
            }
            branch_ops.commit_item("corrupt-feat", "bug", id_str, item)
            ids.append(id_str)

        remote_url = _git(isolated_repo, "remote", "get-url", "origin")
        sibling = isolated_repo.parent / "sibling-corrupt"
        if sibling.exists():
            shutil.rmtree(sibling)
        subprocess.run(
            ["git", "clone", "--branch", "bug-backlog-files",
             remote_url, str(sibling)],
            check=True, capture_output=True,
        )
        try:
            _git(sibling, "config", "user.email", "sib@test.invalid")
            _git(sibling, "config", "user.name", "Sib")
            bad_dir = (sibling / "rabbit" / "features" / "corrupt-feat"
                       / "bugs" / "CORRUPT-FEAT-BUG-998")
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "item.json").write_text("nope")
            _git(sibling, "add", str((bad_dir / "item.json").relative_to(sibling)))
            _git(sibling, "commit", "-m", "inject corrupt")
            _git(sibling, "push", "origin", "HEAD:bug-backlog-files")
        finally:
            shutil.rmtree(sibling, ignore_errors=True)

        items = branch_ops.read_branch(feature="corrupt-feat")
        valid_names = {i["name"] for i in items}
        for valid_id in ids:
            assert valid_id in valid_names
        assert "CORRUPT-FEAT-BUG-998" not in valid_names


# ---------------------------------------------------------------------------
# Tests: orphan-init tmp directory cleaned up on init failure
# ---------------------------------------------------------------------------

class TestInitFailureCleanup:
    def test_orphan_init_tmp_cleaned_on_failure(self, isolated_repo,
                                                monkeypatch):
        """If _init_orphan_branch raises midway, the tmp/branch-init-tmp
        directory MUST still be cleaned up (try/finally)."""
        original_git = branch_ops._git

        def maybe_failing_git(repo, *args):
            if "push" in args and "branch-init-tmp" in str(repo):
                raise RuntimeError("simulated init push failure")
            return original_git(repo, *args)

        monkeypatch.setattr(branch_ops, "_git", maybe_failing_git)

        with pytest.raises(RuntimeError, match="simulated init push failure"):
            branch_ops._init_orphan_branch(str(isolated_repo))

        tmp = Path(isolated_repo) / ".claude" / "tmp" / "branch-init-tmp"
        assert not tmp.exists(), (
            f"branch-init-tmp was not cleaned up after init failure: {tmp}"
        )


# ---------------------------------------------------------------------------
# Tests: release_id branch behaviour
# ---------------------------------------------------------------------------

class TestReleaseIdBranches:
    def test_release_id_rejects_malformed_id_string(self, isolated_repo):
        """An id_str without a numeric trailing segment returns False
        without touching the worktree."""
        assert branch_ops.release_id("rf", "bug", "no-trailing-number") is False

    def test_release_id_decrements_counter_when_safe(self, isolated_repo):
        """After allocate_id reserves ID N+1, release_id rolls back when no
        other process has allocated above it."""
        id_str = branch_ops.allocate_id("rollback-feat", "bug")
        branch_ops.release_id("rollback-feat", "bug", id_str)
        next_id = branch_ops.allocate_id("rollback-feat", "bug")
        assert next_id == "ROLLBACK-FEAT-BUG-1", (
            f"after release_id, next allocate should reuse ID 1, got {next_id}"
        )

    def test_release_id_noop_when_slot_consumed_above(self, isolated_repo):
        """If another allocation happened after our reservation, release_id
        is a no-op (best-effort): the counter is NOT moved."""
        id1 = branch_ops.allocate_id("noop-feat", "bug")
        id2 = branch_ops.allocate_id("noop-feat", "bug")
        branch_ops.release_id("noop-feat", "bug", id1)
        id3 = branch_ops.allocate_id("noop-feat", "bug")
        assert id3 == "NOOP-FEAT-BUG-3", (
            f"release_id must not move counter when slot was consumed above, got {id3}"
        )

    def test_release_id_returns_false_when_slot_overtaken(self, isolated_repo):
        """release_id returns False when counter has advanced past N+1."""
        first = branch_ops.allocate_id("rf", "bug")
        second = branch_ops.allocate_id("rf", "bug")
        assert first.endswith("-1")
        assert second.endswith("-2")
        released = branch_ops.release_id("rf", "bug", first)
        assert released is False

    def test_release_id_returns_false_on_nonretryable_push_error(
            self, isolated_repo, monkeypatch):
        """If the rollback push fails with a non-retryable error, release_id
        is best-effort and returns False."""
        id_str = branch_ops.allocate_id("rf-nonretry", "bug")

        original_run = subprocess.run
        wt_marker = "bug-backlog-files-"

        def wrapped_run(cmd, *args, **kwargs):
            is_push_from_wt = (
                isinstance(cmd, list) and len(cmd) >= 4
                and cmd[0].endswith("git")
                and "push" in cmd
                and any(wt_marker in str(c) for c in cmd)
            )
            if is_push_from_wt:
                class Fake:
                    returncode = 1
                    stderr = "fatal: remote: permission denied\n"
                    stdout = ""
                return Fake()
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(branch_ops.subprocess, "run", wrapped_run)
        assert branch_ops.release_id("rf-nonretry", "bug", id_str) is False

    def test_release_id_returns_false_after_retry_exhaustion(
            self, isolated_repo, monkeypatch):
        """If every push during rollback is non-fast-forward across the
        configured budget, release_id gives up and returns False."""
        id_str = branch_ops.allocate_id("rf-exhaust", "bug")

        original_run = subprocess.run
        wt_marker = "bug-backlog-files-"
        push_attempts = {"count": 0}

        def wrapped_run(cmd, *args, **kwargs):
            is_push_from_wt = (
                isinstance(cmd, list) and len(cmd) >= 4
                and cmd[0].endswith("git")
                and "push" in cmd
                and any(wt_marker in str(c) for c in cmd)
            )
            if is_push_from_wt:
                push_attempts["count"] += 1

                class Fake:
                    returncode = 1
                    stderr = (
                        "To origin\n ! [rejected] HEAD -> bug-backlog-files "
                        "(non-fast-forward)\n"
                    )
                    stdout = ""
                return Fake()
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(branch_ops.subprocess, "run", wrapped_run)
        result = branch_ops.release_id("rf-exhaust", "bug", id_str)
        assert result is False
        assert push_attempts["count"] == branch_ops._MAX_PUSH_ATTEMPTS, (
            f"expected exactly {branch_ops._MAX_PUSH_ATTEMPTS} push attempts, "
            f"got {push_attempts['count']}"
        )


# ---------------------------------------------------------------------------
# Tests: _run_git_with_lock_retry branch behaviour
# ---------------------------------------------------------------------------

class TestRunGitWithLockRetry:
    def test_succeeds_on_retry_after_transient_lock(self, monkeypatch):
        original_run = subprocess.run
        call = {"n": 0}

        def fake_run(cmd, *args, **kwargs):
            call["n"] += 1
            if call["n"] == 1:
                class Fake:
                    returncode = 128
                    stderr = "fatal: Unable to create '.git/index.lock': File exists.\n"
                    stdout = ""
                return Fake()

            class Ok:
                returncode = 0
                stderr = ""
                stdout = ""
            return Ok()

        monkeypatch.setattr(branch_ops.subprocess, "run", fake_run)
        monkeypatch.setattr(branch_ops.time, "sleep", lambda *_: None)

        result = branch_ops._run_git_with_lock_retry(
            ["git", "status"], max_attempts=3
        )
        assert result.returncode == 0
        assert call["n"] == 2

    def test_raises_immediately_on_non_lock_error(self, monkeypatch):
        sleep_calls = {"n": 0}

        def fake_run(cmd, *args, **kwargs):
            class Fake:
                returncode = 1
                stderr = "fatal: not a git repository\n"
                stdout = ""
            return Fake()

        def fake_sleep(*_):
            sleep_calls["n"] += 1

        monkeypatch.setattr(branch_ops.subprocess, "run", fake_run)
        monkeypatch.setattr(branch_ops.time, "sleep", fake_sleep)

        with pytest.raises(RuntimeError) as exc_info:
            branch_ops._run_git_with_lock_retry(
                ["git", "bogus-command"], max_attempts=3
            )
        assert "not a git repository" in str(exc_info.value)
        assert sleep_calls["n"] == 0

    def test_raises_after_exhausting_attempts(self, monkeypatch):
        calls = {"n": 0}

        def fake_run(cmd, *args, **kwargs):
            calls["n"] += 1

            class Fake:
                returncode = 128
                stderr = "fatal: Unable to create '.git/index.lock': File exists.\n"
                stdout = ""
            return Fake()

        monkeypatch.setattr(branch_ops.subprocess, "run", fake_run)
        monkeypatch.setattr(branch_ops.time, "sleep", lambda *_: None)

        with pytest.raises(RuntimeError) as exc_info:
            branch_ops._run_git_with_lock_retry(
                ["git", "fetch", "origin"], max_attempts=4
            )
        assert calls["n"] == 4
        assert ("index.lock" in str(exc_info.value).lower()
                or "lock" in str(exc_info.value).lower())


# ---------------------------------------------------------------------------
# Tests: standalone-topology posture (no defensive local-origin guard)
# ---------------------------------------------------------------------------

class TestStandaloneTopology:
    def test_allocate_id_surfaces_runtime_error_on_misconfigured_local_origin(
            self, tmp_path, monkeypatch):
        """An operator who misconfigures `origin` to a non-existent local path
        will surface a normal git error on first push attempt. There is no
        defensive local-origin guard; allocate_id MUST raise RuntimeError
        with a non-empty diagnostic."""
        local = tmp_path / "bad-origin-local"
        subprocess.run(["git", "init", str(local)], check=True,
                       capture_output=True)
        _git(local, "config", "user.email", "test@test.invalid")
        _git(local, "config", "user.name", "Test")
        (local / "README").write_text("init")
        _git(local, "add", ".")
        _git(local, "commit", "-m", "init")
        bad_origin = tmp_path / "does-not-exist"
        _git(local, "remote", "add", "origin", str(bad_origin))

        monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(local))

        with pytest.raises(RuntimeError) as exc_info:
            branch_ops.allocate_id("rabbit-cage", "bug")
        msg = str(exc_info.value)
        assert msg.strip(), (
            f"RuntimeError must carry a non-empty diagnostic, got {msg!r}"
        )


# ---------------------------------------------------------------------------
# Entry point for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
