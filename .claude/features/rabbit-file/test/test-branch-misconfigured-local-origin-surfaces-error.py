#!/usr/bin/env python3
"""E2E regression test (BACKLOG-13 / F4).

Spec invariant under test:
  An operator who misconfigures `origin` to a non-existent local filesystem
  path will surface a normal git error on first push attempt. There is no
  defensive local-origin guard; the BACKLOG-12 spec removal asserts the
  error must flow through as a normal git failure.

Failure mode:
  - origin URL set to a path that does not exist.
  - Calling allocate_id MUST raise RuntimeError. The diagnostic MUST carry
    a non-empty stderr message (not silent).
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
        raise RuntimeError(f"git {args} failed: {result.stderr}")
    return result.stdout.strip()


@pytest.fixture()
def repo_with_bad_origin(tmp_path):
    """A working clone whose `origin` points at a non-existent local path."""
    local = tmp_path / "local"
    subprocess.run(["git", "init", str(local)], check=True, capture_output=True)
    _git(local, "config", "user.email", "test@test.invalid")
    _git(local, "config", "user.name", "Test")

    (local / "README").write_text("init")
    _git(local, "add", ".")
    _git(local, "commit", "-m", "init")

    bad_origin = tmp_path / "does-not-exist"
    _git(local, "remote", "add", "origin", str(bad_origin))

    yield local

    tmp_dir = local / ".claude" / "tmp"
    if tmp_dir.exists():
        for child in tmp_dir.iterdir():
            if child.name.startswith("bug-backlog-files"):
                shutil.rmtree(child, ignore_errors=True)
    subprocess.run(["git", "-C", str(local), "worktree", "prune"],
                   capture_output=True)


@pytest.fixture(autouse=True)
def patch_repo_root(repo_with_bad_origin, monkeypatch):
    monkeypatch.setattr(
        branch_ops, "_get_repo_root", lambda: str(repo_with_bad_origin))


def test_allocate_id_surfaces_runtime_error_on_misconfigured_local_origin(
        repo_with_bad_origin):
    """allocate_id MUST raise RuntimeError with a non-empty diagnostic when
    origin is a non-existent local path. The error flows through as a
    normal git failure (no defensive guard)."""
    with pytest.raises(RuntimeError) as exc_info:
        branch_ops.allocate_id("rabbit-cage", "bug")
    msg = str(exc_info.value)
    assert msg.strip(), (
        f"RuntimeError must carry a non-empty diagnostic, got {msg!r}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
