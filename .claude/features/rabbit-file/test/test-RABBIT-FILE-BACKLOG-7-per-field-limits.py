#!/usr/bin/env python3
"""
RABBIT-FILE-BACKLOG-7: per-field length limits for title/description.

Enforced symmetrically by BOTH file-item.py (filing time) and
item-status.py update (mutation time):
    MAX_TITLE_LEN       = 200
    MAX_DESCRIPTION_LEN = 10240

The old shared 500-char cap is GONE.
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


@pytest.fixture(autouse=True)
def patch_repo_root(isolated_repo, monkeypatch):
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))


def _run_file_item(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "file-item.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone),
    )


def _run_status(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "item-status.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone),
    )


def _file_minimal(clone, title="t", description="d", feature="lf"):
    r = _run_file_item(
        clone,
        "--type", "bug", "--feature", feature,
        "--title", title, "--priority", "high",
        "--description", description,
    )
    assert r.returncode == 0, r.stderr
    # Filed: <ID>  sha: <sha>
    id_str = r.stdout.split()[1]
    return id_str


# ---------------------------------------------------------------------------
# (a) file-item.py title length boundary
# ---------------------------------------------------------------------------

class TestFileItemTitleLength:
    def test_title_at_200_accepted(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "x" * 200, "--priority", "high",
            "--description", "d",
        )
        assert r.returncode == 0, r.stderr

    def test_title_201_rejected(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "x" * 201, "--priority", "high",
            "--description", "d",
        )
        assert r.returncode != 0
        assert "title" in r.stderr
        assert "200" in r.stderr


# ---------------------------------------------------------------------------
# (b) file-item.py description length boundary
# ---------------------------------------------------------------------------

class TestFileItemDescriptionLength:
    def test_description_at_10240_accepted(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", "y" * 10240,
        )
        assert r.returncode == 0, r.stderr

    def test_description_10241_rejected(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", "y" * 10241,
        )
        assert r.returncode != 0
        assert "description" in r.stderr
        assert "10240" in r.stderr


# ---------------------------------------------------------------------------
# (c) item-status.py update --field title boundary
# ---------------------------------------------------------------------------

class TestUpdateTitleLength:
    def test_title_at_200_accepted(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "title", "--value", "x" * 200,
            "--reason", "boundary",
        )
        assert r.returncode == 0, r.stderr

    def test_title_201_rejected(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "title", "--value", "x" * 201,
            "--reason", "boundary",
        )
        assert r.returncode != 0
        assert "title" in r.stderr
        assert "200" in r.stderr


# ---------------------------------------------------------------------------
# (d) item-status.py update --field description boundary
# ---------------------------------------------------------------------------

class TestUpdateDescriptionLength:
    def test_description_at_10240_accepted(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", "y" * 10240,
            "--reason", "boundary",
        )
        assert r.returncode == 0, r.stderr

    def test_description_10241_rejected(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", "y" * 10241,
            "--reason", "boundary",
        )
        assert r.returncode != 0
        assert "description" in r.stderr
        assert "10240" in r.stderr


# ---------------------------------------------------------------------------
# (e) Symmetry: oversized description rejected by BOTH scripts consistently
# ---------------------------------------------------------------------------

class TestSymmetry:
    def test_file_item_and_update_reject_oversize_description(self, isolated_repo):
        oversize = "z" * 10241

        # file-item.py rejects.
        r_file = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", oversize,
        )
        assert r_file.returncode != 0
        assert "description" in r_file.stderr
        assert "10240" in r_file.stderr

        # update rejects too.
        id_str = _file_minimal(isolated_repo)
        r_upd = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", oversize,
            "--reason", "test",
        )
        assert r_upd.returncode != 0
        assert "description" in r_upd.stderr
        assert "10240" in r_upd.stderr


# ---------------------------------------------------------------------------
# (f) Old 500-char limit is gone: 501-char description now succeeds
# ---------------------------------------------------------------------------

class TestOldLimitRemoved:
    def test_update_501_char_description_succeeds(self, isolated_repo):
        id_str = _file_minimal(isolated_repo)
        r = _run_status(
            isolated_repo, "update",
            "--feature", "lf", "--type", "bug", "--id", id_str,
            "--field", "description", "--value", "d" * 501,
            "--reason", "old limit gone",
        )
        assert r.returncode == 0, r.stderr

    def test_file_item_501_char_description_succeeds(self, isolated_repo):
        r = _run_file_item(
            isolated_repo,
            "--type", "bug", "--feature", "lf",
            "--title", "t", "--priority", "high",
            "--description", "d" * 501,
        )
        assert r.returncode == 0, r.stderr
