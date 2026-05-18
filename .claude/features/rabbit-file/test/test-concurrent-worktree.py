#!/usr/bin/env python3
"""
E2E tests for unique-per-process worktree path and push retry behaviour.

Spec invariants under test:
  - branch_ops.py MUST use git worktree at a UNIQUE per-process path under
    .claude/tmp/ for all writes. The path format is
    .claude/tmp/bug-backlog-files-<pid> where <pid> is the current process ID.
    The legacy fixed path .claude/tmp/bug-backlog-files MUST NOT be used.
  - branch_ops push operations MUST be wrapped in a retry loop with up to 3
    attempts. On non-fast-forward push failure the retry MUST re-fetch
    origin/bug-backlog-files, reset the worktree branch, re-apply local
    changes (re-allocate a fresh ID if needed), and retry the commit+push.
"""

import json
import os
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
        capture_output=True, text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args} failed: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture()
def isolated_repo(tmp_path):
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

    # Clean up any leftover per-process worktrees
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


# ---------------------------------------------------------------------------
# Tests: unique per-process worktree path
# ---------------------------------------------------------------------------

class TestUniqueWorktreePath:
    def test_worktree_path_includes_pid(self, isolated_repo):
        """_worktree() must yield a path matching bug-backlog-files-<pid>."""
        pid = os.getpid()
        expected_name = f"bug-backlog-files-{pid}"
        with branch_ops._worktree(str(isolated_repo)) as wt:
            assert wt.name == expected_name, (
                f"worktree path name={wt.name} does not match "
                f"expected pid-suffixed name={expected_name}"
            )
            # And it must live under .claude/tmp/
            assert wt.parent == Path(isolated_repo) / ".claude" / "tmp"

    def test_legacy_fixed_path_not_created(self, isolated_repo):
        """The legacy fixed path .claude/tmp/bug-backlog-files must not appear."""
        legacy = Path(isolated_repo) / ".claude" / "tmp" / "bug-backlog-files"
        branch_ops.allocate_id("legacy-check", "bug")
        assert not legacy.exists(), (
            f"legacy fixed path {legacy} must not be created"
        )

    def test_worktree_cleaned_up_per_process(self, isolated_repo):
        """Per-process worktree must be removed after operation."""
        pid = os.getpid()
        wt_path = Path(isolated_repo) / ".claude" / "tmp" / f"bug-backlog-files-{pid}"
        branch_ops.allocate_id("cleanup-pid", "bug")
        assert not wt_path.exists(), (
            f"per-process worktree {wt_path} was not cleaned up"
        )


# ---------------------------------------------------------------------------
# Tests: concurrent filing
# ---------------------------------------------------------------------------

class TestConcurrentFiling:
    def test_concurrent_file_item_subprocesses_all_succeed(self, isolated_repo):
        """
        Spawn 3 file-item.py subprocesses in parallel against the same
        feature. All MUST succeed, produce distinct IDs, and leave no stale
        per-process worktrees.
        """
        # Prime the branch so subprocesses don't race on orphan-branch init.
        branch_ops.allocate_id("concurrent-feat", "bug")

        file_item = SCRIPTS_DIR / "file-item.py"
        env = os.environ.copy()
        # Point branch_ops at the isolated repo via cwd
        procs = []
        for i in range(3):
            p = subprocess.Popen(
                [sys.executable, str(file_item),
                 "--type", "bug",
                 "--feature", "concurrent-feat",
                 "--title", f"concurrent bug {i}",
                 "--priority", "low",
                 "--description", f"concurrent test {i}",
                 "--filed-by", "tester"],
                cwd=str(isolated_repo),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            procs.append(p)

        results = []
        for p in procs:
            stdout, stderr = p.communicate(timeout=120)
            results.append((p.returncode, stdout.decode(), stderr.decode()))

        # All must succeed
        for rc, out, err in results:
            assert rc == 0, (
                f"file-item.py subprocess failed: rc={rc} "
                f"stdout={out!r} stderr={err!r}"
            )
            assert "Filed:" in out, f"expected 'Filed:' in stdout, got {out!r}"

        # All IDs must be distinct
        ids = []
        for _, out, _ in results:
            for line in out.splitlines():
                if line.startswith("Filed:"):
                    # Filed: CONCURRENT-FEAT-BUG-N  sha: ...
                    parts = line.split()
                    ids.append(parts[1])
                    break
        assert len(ids) == 3
        assert len(set(ids)) == 3, f"duplicate IDs allocated: {ids}"

        # No stale per-process worktrees should remain
        tmp_dir = Path(isolated_repo) / ".claude" / "tmp"
        if tmp_dir.exists():
            leftover = [p for p in tmp_dir.iterdir()
                        if p.name.startswith("bug-backlog-files")]
            assert leftover == [], (
                f"stale worktrees left behind: {leftover}"
            )


# ---------------------------------------------------------------------------
# Tests: push retry on non-fast-forward
# ---------------------------------------------------------------------------

class TestPushRetry:
    def _competing_commit_then_call(self, isolated_repo, call_fn):
        """
        Install a pre-push hook of sorts: monkey-patch _git so the first
        push attempt is preceded by a competing push from a sibling clone.
        Implemented by wrapping subprocess.run via a one-shot flag.

        Simpler approach: directly trigger a competing commit between
        worktree-checkout and push using a monkeypatched commit step.
        """
        raise NotImplementedError  # See concrete tests below.

    def test_allocate_id_retries_on_non_fast_forward(self, isolated_repo,
                                                     monkeypatch):
        """
        Simulate a non-fast-forward by pushing a competing commit to
        origin/bug-backlog-files AFTER allocate_id has read counter.json
        but BEFORE it pushes. The retry loop must re-fetch, reset, re-read
        counter, allocate the next free ID, and succeed.
        """
        # Prime the branch.
        branch_ops.allocate_id("retry-feat", "bug")  # ID 1

        original_run = subprocess.run
        competing_fired = {"done": False}
        wt_marker = "bug-backlog-files-"  # per-process wt path fragment

        def wrapped_run(cmd, *args, **kwargs):
            # Intercept the FIRST `git push` call from branch_ops' own
            # worktree (path contains bug-backlog-files-<pid>). Fire a
            # competing commit, then let the push proceed (which will fail
            # with non-fast-forward and trigger the retry).
            is_push_from_wt = (
                not competing_fired["done"]
                and isinstance(cmd, list) and len(cmd) >= 4
                and cmd[0].endswith("git")
                and "push" in cmd
                and any(wt_marker in str(c) for c in cmd)
            )
            if is_push_from_wt:
                competing_fired["done"] = True
                _inject_competing_commit(isolated_repo, "retry-feat")
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(branch_ops.subprocess, "run", wrapped_run)

        # This call must succeed via retry even though the first push fails
        # with non-fast-forward.
        new_id = branch_ops.allocate_id("retry-feat", "bug")
        assert new_id, "allocate_id must return an ID after retry"
        # The competing commit reserved ID 2, so retry must pick ID 3.
        assert new_id == "RETRY-FEAT-BUG-3", (
            f"after retry, expected RETRY-FEAT-BUG-3, got {new_id}"
        )

    def test_push_gives_up_after_3_attempts(self, isolated_repo, monkeypatch):
        """
        If non-fast-forward persists across 3 attempts, allocate_id raises
        RuntimeError with a clear diagnostic mentioning the retry exhaustion.
        Also counts push attempts to verify exactly 3 attempts were made.
        """
        branch_ops.allocate_id("giveup-feat", "bug")

        original_run = subprocess.run
        push_attempts = {"count": 0}
        wt_marker = "bug-backlog-files-"

        def wrapped_run(cmd, *args, **kwargs):
            # Inject a competing commit before every push attempt FROM the
            # branch_ops worktree (path contains bug-backlog-files-<pid>),
            # so non-fast-forward persists across attempts. Other push
            # commands (from injection helper itself) are passed through.
            is_push_from_wt = (
                isinstance(cmd, list) and len(cmd) >= 4
                and cmd[0].endswith("git")
                and "push" in cmd
                and any(wt_marker in str(c) for c in cmd)
            )
            if is_push_from_wt:
                push_attempts["count"] += 1
                _inject_competing_commit(isolated_repo, "giveup-feat")
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(branch_ops.subprocess, "run", wrapped_run)

        with pytest.raises(RuntimeError) as exc_info:
            branch_ops.allocate_id("giveup-feat", "bug")

        # Must have attempted at least 3 times (spec floor) before giving up.
        assert push_attempts["count"] >= 3, (
            f"expected at least 3 push attempts, got {push_attempts['count']}"
        )
        # Match the implementation's bounded retry count exactly.
        assert push_attempts["count"] == branch_ops._MAX_PUSH_ATTEMPTS, (
            f"expected {branch_ops._MAX_PUSH_ATTEMPTS} push attempts "
            f"(impl _MAX_PUSH_ATTEMPTS), got {push_attempts['count']}"
        )
        # Error message must reference the retry exhaustion.
        msg = str(exc_info.value).lower()
        assert "attempt" in msg or "retry" in msg or str(branch_ops._MAX_PUSH_ATTEMPTS) in msg, (
            f"error message must mention retry exhaustion, got: {exc_info.value}"
        )


# ---------------------------------------------------------------------------
# Tests: commit_item's commit_sha-backfill push uses retry parity (BUG-14)
# ---------------------------------------------------------------------------


class TestBackfillPushRetry:
    """The second push in commit_item (commit_sha backfill) MUST use the
    same retry-with-fetch+reset+reapply mechanism as the primary push. A
    silent failure on the backfill push leaves item.json without commit_sha
    and breaks every downstream consumer (PR creation, release notes)."""

    def test_backfill_push_retries_on_non_fast_forward(self, isolated_repo,
                                                       monkeypatch):
        """Inject a competing commit AFTER the primary item push succeeds
        but BEFORE the backfill push. The backfill must retry, re-fetch,
        re-apply the commit_sha write on top of the fresh tip, and succeed
        — leaving item.json with commit_sha populated."""
        # Prime the branch and reserve an ID.
        id_str = branch_ops.allocate_id("backfill-feat", "bug")

        original_run = subprocess.run
        wt_marker = "bug-backlog-files-"
        # State machine: count pushes from the branch_ops worktree.
        # Push 1 = primary item commit. Push 2 = backfill (we inject before it).
        # After we've injected once, allow subsequent pushes through cleanly so
        # the retry can land.
        state = {"wt_pushes": 0, "injected": False}

        def wrapped_run(cmd, *args, **kwargs):
            is_push_from_wt = (
                isinstance(cmd, list) and len(cmd) >= 4
                and cmd[0].endswith("git")
                and "push" in cmd
                and any(wt_marker in str(c) for c in cmd)
            )
            if is_push_from_wt:
                state["wt_pushes"] += 1
                # Inject right before the SECOND wt push (the backfill).
                if state["wt_pushes"] == 2 and not state["injected"]:
                    state["injected"] = True
                    _inject_competing_commit(isolated_repo, "backfill-feat")
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(branch_ops.subprocess, "run", wrapped_run)

        item = {
            "name": id_str, "type": "bug", "title": "Backfill retry test",
            "status": "open", "priority": "low",
            "description": "verify backfill push retries",
            "related_feature": "backfill-feat",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "tester",
            "closed": None, "history": [],
        }

        # Must succeed despite the injected non-fast-forward on the backfill push.
        sha = branch_ops.commit_item("backfill-feat", "bug", id_str, item)
        assert sha, "commit_item must return a non-empty SHA after backfill retry"
        assert state["injected"], "test fixture did not inject competing commit"

        # The fetched item MUST have commit_sha populated; a silent backfill
        # failure would leave it absent.
        fetched = branch_ops.fetch_item("backfill-feat", "bug", id_str)
        assert fetched is not None
        assert fetched.get("commit_sha"), (
            f"commit_sha is missing from item.json after backfill retry; "
            f"fetched={fetched!r}"
        )

    def test_backfill_push_gives_up_after_max_attempts(self, isolated_repo,
                                                       monkeypatch):
        """If non-fast-forward persists on the backfill push across the full
        retry budget, commit_item raises RuntimeError with retry diagnostics.
        Verifies parity with primary push retry budget (_MAX_PUSH_ATTEMPTS)."""
        id_str = branch_ops.allocate_id("backfill-giveup", "bug")

        original_run = subprocess.run
        wt_marker = "bug-backlog-files-"
        state = {"wt_pushes": 0, "backfill_attempts": 0}

        def wrapped_run(cmd, *args, **kwargs):
            is_push_from_wt = (
                isinstance(cmd, list) and len(cmd) >= 4
                and cmd[0].endswith("git")
                and "push" in cmd
                and any(wt_marker in str(c) for c in cmd)
            )
            if is_push_from_wt:
                state["wt_pushes"] += 1
                # Push 1 = primary item (allow through). Pushes 2+ = backfill
                # attempts (inject every time so non-fast-forward persists).
                if state["wt_pushes"] >= 2:
                    state["backfill_attempts"] += 1
                    _inject_competing_commit(isolated_repo, "backfill-giveup")
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(branch_ops.subprocess, "run", wrapped_run)

        item = {
            "name": id_str, "type": "bug", "title": "Backfill giveup",
            "status": "open", "priority": "low",
            "description": "verify backfill retry budget",
            "related_feature": "backfill-giveup",
            "filed": "2026-01-01T00:00:00Z", "filed_by": "tester",
            "closed": None, "history": [],
        }

        with pytest.raises(RuntimeError) as exc_info:
            branch_ops.commit_item("backfill-giveup", "bug", id_str, item)

        # Backfill push must have honoured the full retry budget (parity
        # with primary push).
        assert state["backfill_attempts"] == branch_ops._MAX_PUSH_ATTEMPTS, (
            f"backfill push must attempt exactly _MAX_PUSH_ATTEMPTS="
            f"{branch_ops._MAX_PUSH_ATTEMPTS}, got {state['backfill_attempts']}"
        )
        msg = str(exc_info.value).lower()
        assert (
            "attempt" in msg or "retry" in msg
            or str(branch_ops._MAX_PUSH_ATTEMPTS) in msg
        ), f"error message must mention retry exhaustion, got: {exc_info.value}"


def _inject_competing_commit(isolated_repo, feature):
    """
    Simulate another agent pushing a competing counter.json commit to
    origin/bug-backlog-files. Uses a sibling clone.
    """
    remote_url = _git(isolated_repo, "remote", "get-url", "origin")
    sibling = isolated_repo.parent / f"competing-{os.getpid()}-{id(feature)}"
    if sibling.exists():
        shutil.rmtree(sibling)
    subprocess.run(
        ["git", "clone", "--branch", "bug-backlog-files",
         remote_url, str(sibling)],
        check=True, capture_output=True,
    )
    try:
        _git(sibling, "config", "user.email", "competitor@test.invalid")
        _git(sibling, "config", "user.name", "Competitor")
        counter_dir = sibling / "rabbit" / "features" / feature / "bugs"
        counter_dir.mkdir(parents=True, exist_ok=True)
        counter_file = counter_dir / "counter.json"
        if counter_file.exists():
            cur = json.loads(counter_file.read_text())
            n = cur.get("next", 1)
        else:
            n = 1
        counter_file.write_text(json.dumps({"next": n + 1}))
        _git(sibling, "add", str(counter_file.relative_to(sibling)))
        _git(sibling, "commit", "-m",
             f"competing: reserve {feature.upper()}-BUG-{n}")
        _git(sibling, "push", "origin", "HEAD:bug-backlog-files")
    finally:
        shutil.rmtree(sibling, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
