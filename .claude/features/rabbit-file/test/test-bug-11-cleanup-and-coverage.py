#!/usr/bin/env python3
"""
RABBIT-FILE-BACKLOG-11: dead-code cleanup + test-gap closures.

Covers the gap closures from the BACKLOG-11 impl suggestion:

  - sanitize_text edge cases (empty, all-control, multi-byte, allowed
    whitespace preserved, ESC stripped).
  - validate_field_length boundary behaviour (under, at, over limit).
  - release_id branches:
      * malformed-ID input returns False without touching the worktree.
      * non-retryable push error during rollback returns False.
      * retry exhaustion (every push attempt non-fast-forward) returns False
        and exhausts the configured budget.
  - _run_git_with_lock_retry branches:
      * succeeds on retry after a transient .git/index.lock race.
      * raises immediately on a non-retryable error.
      * raises after exhausting max_attempts on persistent lock contention.

Also enforces the cleanup invariants:
  - The legacy private alias `_BRANCH` is gone (BRANCH is the single
    canonical export).
  - branch_ops module exports release_id and branch_exists in addition to
    the four core entry points named in spec.md.
"""

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


# ---------------------------------------------------------------------------
# Unit tests: sanitize_text
# ---------------------------------------------------------------------------

class TestSanitizeText:
    def test_empty_string(self):
        assert branch_ops.sanitize_text("") == ""

    def test_plain_ascii_unchanged(self):
        assert branch_ops.sanitize_text("hello world") == "hello world"

    def test_allowed_whitespace_preserved(self):
        # tab, newline, carriage return are explicitly preserved.
        assert branch_ops.sanitize_text("a\tb\nc\rd") == "a\tb\nc\rd"

    def test_all_control_chars_stripped(self):
        # NUL through US (0x1f), excluding tab/newline/CR.
        forbidden = "".join(
            chr(i) for i in range(0x20)
            if chr(i) not in ("\t", "\n", "\r")
        )
        assert branch_ops.sanitize_text(forbidden) == ""

    def test_esc_stripped_protects_against_terminal_injection(self):
        # The motivating attack: ESC[2J would clear the user's terminal
        # when list-items.py prints the title.
        evil = "title\x1b[2J\x1b[H"
        assert branch_ops.sanitize_text(evil) == "title[2J[H"

    def test_mixed_content(self):
        # NUL embedded in otherwise-valid text is stripped, surrounding
        # text (including allowed whitespace) is preserved.
        assert (
            branch_ops.sanitize_text("good\x00\tbetter\x07\nbest")
            == "good\tbetter\nbest"
        )

    def test_multi_byte_unicode_preserved(self):
        # Non-ASCII characters are NEVER stripped (they are >= " ").
        text = "rabbit cafe naive éè \U0001f407"
        assert branch_ops.sanitize_text(text) == text


# ---------------------------------------------------------------------------
# Unit tests: validate_field_length
# ---------------------------------------------------------------------------

class TestValidateFieldLength:
    def test_under_limit_passes(self):
        # No exception raised when len(value) < limit.
        branch_ops.validate_field_length("title", "abc", limit=10)

    def test_at_limit_passes(self):
        # Boundary: len(value) == limit is allowed.
        branch_ops.validate_field_length("title", "x" * 10, limit=10)

    def test_one_over_limit_raises(self):
        with pytest.raises(ValueError) as exc_info:
            branch_ops.validate_field_length("title", "x" * 11, limit=10)
        msg = str(exc_info.value)
        # The error must name the field, the limit, and the actual length.
        assert "title" in msg
        assert "10" in msg
        assert "11" in msg

    def test_description_far_over_limit_raises(self):
        big = "z" * (branch_ops.MAX_DESCRIPTION_LEN + 1)
        with pytest.raises(ValueError) as exc_info:
            branch_ops.validate_field_length(
                "description", big, limit=branch_ops.MAX_DESCRIPTION_LEN
            )
        assert "description" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Cleanup invariants (BACKLOG-11)
# ---------------------------------------------------------------------------

class TestCleanupInvariants:
    def test_legacy_underscore_branch_alias_removed(self):
        """The private `_BRANCH` alias must be gone; only the public
        `BRANCH` constant remains."""
        assert hasattr(branch_ops, "BRANCH")
        assert not hasattr(branch_ops, "_BRANCH"), (
            "_BRANCH legacy alias must be deleted (BACKLOG-11 cleanup)"
        )

    def test_module_exports_release_id_and_branch_exists(self):
        """spec.md Exposes list must include release_id and branch_exists
        — the public API has grown since the initial implementation."""
        assert callable(getattr(branch_ops, "release_id", None))
        assert callable(getattr(branch_ops, "branch_exists", None))


# ---------------------------------------------------------------------------
# release_id branch-coverage tests
# ---------------------------------------------------------------------------

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

    tmp_dir = local / ".claude" / "tmp"
    if tmp_dir.exists():
        for child in tmp_dir.iterdir():
            if child.name.startswith("bug-backlog-files"):
                shutil.rmtree(child, ignore_errors=True)
    subprocess.run(["git", "-C", str(local), "worktree", "prune"],
                   capture_output=True)


@pytest.fixture()
def patch_repo_root(isolated_repo, monkeypatch):
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))


class TestReleaseIdBranches:
    def test_release_id_rejects_malformed_id_string(self, patch_repo_root):
        """An id_str without a numeric trailing segment returns False
        without touching the worktree (the early-return guard)."""
        assert branch_ops.release_id("rf", "bug", "no-trailing-number") is False

    def test_release_id_returns_false_when_slot_overtaken(
            self, isolated_repo, patch_repo_root):
        """If the counter has advanced past N+1 (another process allocated
        on top), release_id leaves the counter alone and returns False."""
        # Allocate IDs 1 and 2; then try to release "RF-BUG-1" (whose
        # rollback would only be safe if counter were still 2).
        first = branch_ops.allocate_id("rf", "bug")
        second = branch_ops.allocate_id("rf", "bug")
        assert first.endswith("-1")
        assert second.endswith("-2")
        # Counter is now at 3. Releasing N=1 is unsafe -> False.
        released = branch_ops.release_id("rf", "bug", first)
        assert released is False

    def test_release_id_returns_false_on_nonretryable_push_error(
            self, isolated_repo, patch_repo_root, monkeypatch):
        """If the rollback push fails with a non-retryable error, release_id
        is best-effort and returns False (covers branch 555-557)."""
        # Reserve an ID so the counter is in a rollback-eligible state.
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
                # Return a fake non-retryable failure (e.g. permission
                # denied) so release_id falls into the non-retryable branch.
                class Fake:
                    returncode = 1
                    stderr = "fatal: remote: permission denied\n"
                    stdout = ""
                return Fake()
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(branch_ops.subprocess, "run", wrapped_run)
        assert branch_ops.release_id("rf-nonretry", "bug", id_str) is False

    def test_release_id_returns_false_after_retry_exhaustion(
            self, isolated_repo, patch_repo_root, monkeypatch):
        """If every push during rollback is non-fast-forward across the
        configured budget, release_id gives up and returns False (covers
        branch 558-559)."""
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
                    # Retryable: non-fast-forward
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
# _run_git_with_lock_retry branch-coverage tests
# ---------------------------------------------------------------------------

class TestRunGitWithLockRetry:
    def test_succeeds_on_retry_after_transient_lock(self, monkeypatch):
        """A first-attempt lock race that clears by the second attempt
        results in a successful return — no exception raised."""
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
            # Subsequent call: succeed with a real (or trivially fake) result.
            class Ok:
                returncode = 0
                stderr = ""
                stdout = ""
            return Ok()

        monkeypatch.setattr(branch_ops.subprocess, "run", fake_run)
        # Sleep is jittered; patch it out for test speed.
        monkeypatch.setattr(branch_ops.time, "sleep", lambda *_: None)

        result = branch_ops._run_git_with_lock_retry(
            ["git", "status"], max_attempts=3
        )
        assert result.returncode == 0
        assert call["n"] == 2

    def test_raises_immediately_on_non_lock_error(self, monkeypatch):
        """A non-lock error (e.g. bad command) raises on the FIRST attempt
        — no retry, no sleep."""
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
        # Non-lock errors must NOT trigger a backoff sleep.
        assert sleep_calls["n"] == 0

    def test_raises_after_exhausting_attempts(self, monkeypatch):
        """Persistent lock contention exhausts max_attempts and raises."""
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
        # Diagnostic mentions the failure detail.
        assert "index.lock" in str(exc_info.value).lower() or "lock" in str(exc_info.value).lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
