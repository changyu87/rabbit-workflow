#!/usr/bin/env python3
"""Tests for item-status.py"""
import json
import subprocess
import sys
from datetime import timezone, datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
TEST_DIR = Path(__file__).parent


@pytest.fixture
def isolated_repo(tmp_path, monkeypatch):
    import subprocess as sp
    bare = tmp_path / "remote.git"
    bare.mkdir()
    sp.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    clone = tmp_path / "repo"
    sp.run(["git", "clone", str(bare), str(clone)], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "config", "user.name", "Tester"], check=True, capture_output=True)
    branch = sp.run(["git", "-C", str(clone), "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True).stdout.strip() or "main"
    (clone / "README").write_text("init")
    sp.run(["git", "-C", str(clone), "add", "."], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "commit", "-m", "init"], check=True, capture_output=True)
    sp.run(["git", "-C", str(clone), "push", "origin", branch], check=True, capture_output=True)

    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))
    return clone


@pytest.fixture
def filed_item(isolated_repo, monkeypatch):
    """File a bug item and return (clone, id_str)."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(isolated_repo))

    id_str = branch_ops.allocate_id("test-feat", "bug")
    item = {
        "name": id_str, "type": "bug", "title": "Test", "status": "open",
        "priority": "high", "description": "desc", "related_feature": "test-feat",
        "filed": "2026-01-01T00:00:00Z", "filed_by": "tester", "closed": None,
        "history": [{"ts": "2026-01-01T00:00:00Z", "actor": "tester", "action": "opened", "note": "initial filing"}],
    }
    branch_ops.commit_item("test-feat", "bug", id_str, item)
    return isolated_repo, id_str


def run_cmd(clone, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "item-status.py")] + list(args),
        capture_output=True, text=True, cwd=str(clone)
    )


def test_get_returns_status(filed_item):
    clone, id_str = filed_item
    r = run_cmd(clone, "get", "--feature", "test-feat", "--type", "bug", "--id", id_str)
    assert r.returncode == 0
    assert r.stdout.strip() == "open"


def test_get_missing_item_exits_1(isolated_repo):
    r = run_cmd(isolated_repo, "get", "--feature", "test-feat", "--type", "bug", "--id", "MISSING-1")
    assert r.returncode == 1


def test_set_missing_reason_exits_1(filed_item):
    clone, id_str = filed_item
    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "close")
    assert r.returncode != 0


def test_set_open_to_close(filed_item, monkeypatch):
    clone, id_str = filed_item
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))

    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "close", "--reason", "fixed it")
    assert r.returncode == 0, r.stderr
    assert f"Status set: {id_str} -> close" in r.stdout

    item = branch_ops.fetch_item("test-feat", "bug", id_str)
    assert item["status"] == "close"
    assert item["closed"] is not None
    assert item["history"][-1]["action"] == "closed"
    assert item["history"][-1]["note"] == "fixed it"


def test_set_close_to_open(filed_item, monkeypatch):
    clone, id_str = filed_item
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))

    # First close it
    run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
            "--id", id_str, "--status", "close", "--reason", "done")
    # Then reopen
    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "open", "--reason", "actually not done")
    assert r.returncode == 0, r.stderr

    item = branch_ops.fetch_item("test-feat", "bug", id_str)
    assert item["status"] == "open"
    assert item["closed"] is None
    assert item["history"][-1]["action"] == "opened"


def test_set_with_fix_commits(filed_item, monkeypatch):
    clone, id_str = filed_item
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import branch_ops
    monkeypatch.setattr(branch_ops, "_get_repo_root", lambda: str(clone))

    r = run_cmd(clone, "set", "--feature", "test-feat", "--type", "bug",
                "--id", id_str, "--status", "close", "--reason", "fixed",
                "--fix-commits", "abc123def456")
    assert r.returncode == 0, r.stderr

    item = branch_ops.fetch_item("test-feat", "bug", id_str)
    assert item["history"][-1]["fix_commits"] == "abc123def456"
