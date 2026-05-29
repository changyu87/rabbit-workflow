"""Shared pytest fixtures for the rabbit-issue test suite.

Provides:
  - gh_shim: puts gh_shim.sh on PATH as `gh` and exposes the call log.
  - fake_repo: a throwaway git repo whose origin is a fake GitHub URL.

These fixtures are unused in Phase 1 (only static-check tests exist),
but the runtime-script TDD phases (Phase 2 onward) need them per the
rabbit-issue implementation plan.
"""
import os
import subprocess
from pathlib import Path

import pytest

TEST_DIR = Path(__file__).parent
SHIM = TEST_DIR / "gh_shim.sh"


@pytest.fixture
def gh_shim(monkeypatch, tmp_path):
    """Put gh_shim.sh on PATH as `gh`. Returns the log path."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").symlink_to(SHIM)
    log = tmp_path / "gh.log"
    log.write_text("")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("GH_SHIM_LOG", str(log))
    return log


@pytest.fixture
def fake_repo(monkeypatch, tmp_path):
    """A throwaway git repo with origin set to a fake GH URL."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin",
         "https://github.com/test/repo.git"],
        check=True,
    )
    monkeypatch.chdir(repo)
    return repo
