#!/usr/bin/env python3
"""
E2E test for RABBIT-FILE-BUG-32: chained-workspace orphan-branch guard.

Spec invariant under test:
  branch_ops._ensure_branch MUST refuse to create a new orphan
  bug-backlog-files branch when the immediate origin is a local
  filesystem path (starts with `/`, `file://`, or otherwise does not
  look like a network URL — no `://` and no `git@`).

  In a chained-workspace topology (e.g. ws-child -> ws-parent -> GitHub)
  the upstream branch may exist genuinely on GitHub but be absent from
  the intermediate's refs/heads/, so the existing
  `ls-remote --heads origin bug-backlog-files` check returns False.
  Silently calling `_init_orphan_branch` in this case would push a
  fresh, empty branch to the intermediate and overwrite the legitimate
  items at the upstream-of-upstream once divergence is resolved.

  `_ensure_branch` MUST instead raise RuntimeError whose message names:
    - the immediate origin URL,
    - the branch name (BRANCH constant),
    - the remediation: operator runs `git -C <intermediate> fetch ...`
      then `git -C <intermediate> checkout bug-backlog-files`.

  A true fresh-repo bootstrap against a remote (HTTPS or SSH) origin
  that lacks the branch continues to create the orphan as before.
"""

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
        raise RuntimeError(f"git {args} failed in {repo}: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture()
def chained_repos(tmp_path):
    """
    Simulate a chained-workspace topology:
      child repo's origin = parent repo's filesystem path
      parent repo has NO refs/heads/bug-backlog-files
    """
    parent = tmp_path / "parent"
    parent.mkdir()
    subprocess.run(["git", "init", str(parent)], check=True, capture_output=True)
    _git(parent, "config", "user.email", "parent@test.invalid")
    _git(parent, "config", "user.name", "Parent")
    (parent / "README").write_text("parent")
    _git(parent, "add", ".")
    _git(parent, "commit", "-m", "init parent")

    child = tmp_path / "child"
    subprocess.run(
        ["git", "clone", str(parent), str(child)],
        check=True, capture_output=True
    )
    _git(child, "config", "user.email", "child@test.invalid")
    _git(child, "config", "user.name", "Child")

    yield {"parent": parent, "child": child}

    tmp_dir = child / ".claude" / "tmp"
    if tmp_dir.exists():
        for sub in tmp_dir.iterdir():
            if sub.name.startswith("bug-backlog-files"):
                shutil.rmtree(sub, ignore_errors=True)
    subprocess.run(
        ["git", "-C", str(child), "worktree", "prune"], capture_output=True
    )


def _parent_has_local_branch(parent, branch):
    """Return True iff parent has refs/heads/<branch>."""
    result = subprocess.run(
        ["git", "-C", str(parent), "rev-parse", "--verify",
         f"refs/heads/{branch}"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


class TestChainedWorkspaceGuard:
    def test_ensure_branch_refuses_orphan_creation_when_origin_is_local(
            self, chained_repos, monkeypatch):
        """
        Child's origin is a local filesystem path; parent does NOT have
        refs/heads/bug-backlog-files. _ensure_branch (via allocate_id)
        MUST raise RuntimeError instead of silently calling
        _init_orphan_branch.
        """
        child = chained_repos["child"]
        parent = chained_repos["parent"]
        monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(child))

        assert not _parent_has_local_branch(parent, branch_ops.BRANCH), (
            "fixture setup error: parent should not have the branch yet"
        )

        with pytest.raises(RuntimeError) as exc_info:
            branch_ops.allocate_id("rabbit-cage", "bug")

        msg = str(exc_info.value)
        # The error message must name the origin URL (parent path),
        # the branch name, and the remediation command.
        assert str(parent) in msg, (
            f"error message missing origin URL {parent!s}: {msg}"
        )
        assert branch_ops.BRANCH in msg, (
            f"error message missing branch name {branch_ops.BRANCH!r}: {msg}"
        )
        assert "fetch origin" in msg and branch_ops.BRANCH in msg, (
            f"error message missing fetch remediation: {msg}"
        )
        assert "checkout" in msg, (
            f"error message missing checkout remediation: {msg}"
        )

        # Critically: the parent must STILL not have refs/heads/<branch>.
        # If the guard had failed and _init_orphan_branch had pushed,
        # the parent would now have a fresh orphan branch with no items.
        assert not _parent_has_local_branch(parent, branch_ops.BRANCH), (
            "guard failed: parent now has refs/heads/bug-backlog-files; "
            "an orphan was silently pushed despite local origin"
        )

    def test_ensure_branch_bootstraps_orphan_when_origin_is_remote(
            self, chained_repos, monkeypatch):
        """
        Positive companion: when origin is NOT local (simulated by patching
        _is_local_origin to return False), the existing orphan-bootstrap
        path must still run. This protects the fresh-repo guarantee.
        """
        child = chained_repos["child"]
        parent = chained_repos["parent"]
        monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(child))

        # Pretend origin is remote even though it physically is local.
        # This isolates the guard from the bootstrap path.
        monkeypatch.setattr(branch_ops, "_is_local_origin",
                            lambda repo_root: False)

        # Should NOT raise; allocate_id completes and the branch is
        # created on the (locally-mocked-as-remote) origin.
        id_str = branch_ops.allocate_id("rabbit-cage", "bug")
        assert id_str == "RABBIT-CAGE-BUG-1"

        # Branch now exists on the parent (since the push physically went
        # to the local parent path, even though we treated it as remote).
        assert _parent_has_local_branch(parent, branch_ops.BRANCH)

    @pytest.mark.parametrize("url,expected", [
        ("/srv/git/repo.git", True),
        ("file:///srv/git/repo.git", True),
        ("/home/user/workflow-dev/ws29", True),
        ("relative/path/repo", True),  # no :// and no git@
        ("https://github.com/foo/bar.git", False),
        ("http://example.com/foo.git", False),
        ("git@github.com:foo/bar.git", False),
        ("ssh://git@github.com/foo/bar.git", False),
    ])
    def test_is_local_origin_classification(self, url, expected, monkeypatch):
        """Unit-level companion: _is_local_origin classifies URLs correctly."""
        # Patch git remote get-url to return the test URL regardless of repo.
        real_git = branch_ops._git

        def fake_git(repo, *args):
            if args[:2] == ("remote", "get-url"):
                return url
            return real_git(repo, *args)

        monkeypatch.setattr(branch_ops, "_git", fake_git)
        assert branch_ops._is_local_origin("/fake/repo") is expected


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
