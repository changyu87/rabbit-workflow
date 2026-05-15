#!/usr/bin/env python3
"""Tests for file-item.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"


@pytest.fixture
def isolated_repo(tmp_path, monkeypatch):
    """Create an isolated git repo pair (bare remote + clone) for testing."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

    clone = tmp_path / "repo"
    subprocess.run(["git", "clone", str(bare), str(clone)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.name", "Tester"], check=True, capture_output=True)

    # Make an initial commit so clone has a HEAD
    (clone / "README").write_text("init")
    subprocess.run(["git", "-C", str(clone), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "commit", "-m", "init"], check=True, capture_output=True)
    # Determine actual branch name (may be master or main depending on git config)
    branch_result = subprocess.run(
        ["git", "-C", str(clone), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True, capture_output=True, text=True
    )
    default_branch = branch_result.stdout.strip()
    subprocess.run(["git", "-C", str(clone), "push", "origin", default_branch], check=True, capture_output=True)

    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))
    return clone


def test_missing_title_exits_1(isolated_repo):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "file-item.py"),
         "--type", "bug", "--feature", "test-feat",
         "--priority", "high", "--description", "desc"],
        capture_output=True, text=True, cwd=str(isolated_repo)
    )
    assert r.returncode != 0


def test_missing_priority_exits_1(isolated_repo):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "file-item.py"),
         "--type", "bug", "--feature", "test-feat",
         "--title", "T", "--description", "desc"],
        capture_output=True, text=True, cwd=str(isolated_repo)
    )
    assert r.returncode != 0


def test_invalid_priority_exits_1(isolated_repo):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "file-item.py"),
         "--type", "bug", "--feature", "test-feat",
         "--title", "T", "--priority", "EXTREME", "--description", "desc"],
        capture_output=True, text=True, cwd=str(isolated_repo)
    )
    assert r.returncode != 0
    assert "invalid choice" in r.stderr.lower()


def test_valid_bug_filing(isolated_repo):
    import branch_ops
    branch_ops_mod = __import__("branch_ops")
    # Use branch_ops directly to verify item.json after filing
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "file-item.py"),
         "--type", "bug", "--feature", "test-feat",
         "--title", "Test bug", "--priority", "high",
         "--description", "A test bug", "--filed-by", "tester"],
        capture_output=True, text=True, cwd=str(isolated_repo)
    )
    assert r.returncode == 0, r.stderr
    assert "Filed: TEST-FEAT-BUG-1" in r.stdout
    assert "sha:" in r.stdout
    sha_part = r.stdout.strip().split("sha:")[-1].strip()
    assert len(sha_part) == 40  # full git SHA

    # Verify item.json on the branch
    item = branch_ops_mod.fetch_item("test-feat", "bug", "TEST-FEAT-BUG-1")
    assert item is not None
    assert item["name"] == "TEST-FEAT-BUG-1"
    assert item["type"] == "bug"
    assert item["status"] == "open"
    assert item["priority"] == "high"
    assert item["history"][0]["action"] == "opened"
    assert item["history"][0]["actor"] == "tester"


def test_valid_backlog_filing(isolated_repo):
    import branch_ops as bm
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "file-item.py"),
         "--type", "backlog", "--feature", "test-feat",
         "--title", "Backlog item", "--priority", "low",
         "--description", "A backlog", "--filed-by", "tester"],
        capture_output=True, text=True, cwd=str(isolated_repo)
    )
    assert r.returncode == 0, r.stderr
    assert "BACKLOG" in r.stdout

    item = bm.fetch_item("test-feat", "backlog", "TEST-FEAT-BACKLOG-1")
    assert item is not None
    assert item["type"] == "backlog"
